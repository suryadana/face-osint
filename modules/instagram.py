"""
Instagram scraper — Playwright Async API
"""
import json, re, random, asyncio
from playwright.async_api import async_playwright

from modules import config
from modules.ratelimit import (
    RateLimiter, RequestBudget, backoff_delay,
    detect_soft_block, SoftBlockError, jittered_delay,
)

# Shared browser — one Playwright instance across all Instagram objects
_pw = None
_browser = None
_browser_lock = asyncio.Lock()
_owns_browser = False

async def ensure_browser(headless=True):
    global _pw, _browser
    if _pw is None:
        async with _browser_lock:
            if _pw is None:
                _pw = await async_playwright().start()
                _browser = await _pw.chromium.launch(headless=headless)

async def close_shared_browser():
    global _pw, _browser
    if _browser:
        await _browser.close()
        _browser = None
    if _pw:
        await _pw.stop()
        _pw = None

def parse_cookies(s):
    c = []
    for p in s.split("; "):
        if "=" not in p: continue
        n, v = p.split("=", 1)
        v = v.strip('"')
        if n == "rur":
            v = v.replace("\\054", ",")
        c.append({
            "name": n.strip(), "value": v, "domain": ".instagram.com",
            "path": "/", "httpOnly": n in ("sessionid", "csrftoken", "ds_user_id", "rur"),
            "secure": True, "sameSite": "Lax"
        })
    return c

async def _backoff_wait(attempt):
    delay = backoff_delay(attempt, cap=config.BACKOFF_CAP)
    print(f"  Rate limited, retrying in {delay:.0f}s (attempt {attempt+1})", flush=True)
    await asyncio.sleep(delay)

class Instagram:
    def __init__(self, cookie_string, timeout=15000, skip_home=False,
                 rate_limiter=None, budget=None):
        self.cookie_string = cookie_string
        self.timeout = timeout
        self.skip_home = skip_home
        self.rate_limiter = rate_limiter or RateLimiter(0)
        self.budget = budget or RequestBudget(None)
        self.ctx = None
        self.page = None

    async def __aenter__(self):
        await ensure_browser()
        self.ctx = await _browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        )
        await self.ctx.add_cookies(parse_cookies(self.cookie_string))
        self.page = await self.ctx.new_page()
        if not self.skip_home:
            await self._goto_with_retry("https://www.instagram.com/")
            await self.page.wait_for_timeout(2000)
        return self

    async def __aexit__(self, *args):
        if self.page:
            await self.page.close()
        if self.ctx:
            await self.ctx.close()

    async def _goto_with_retry(self, url, wait_until="domcontentloaded"):
        for attempt in range(5):
            await self.rate_limiter.acquire()
            await self.budget.spend()
            try:
                r = await self.page.goto(url, wait_until=wait_until, timeout=self.timeout)
                final_url = self.page.url
                kind = detect_soft_block(r.status if r else 200, final_url, "")
                if kind:
                    raise SoftBlockError(kind, url)
                if r and r.status == 429:
                    await _backoff_wait(attempt)
                else:
                    return r
            except SoftBlockError:
                raise
            except Exception:
                if attempt == 4:
                    raise
                await _backoff_wait(attempt)

    async def _click_text(self, text):
        # Try exact match first
        try:
            el = self.page.get_by_text(text, exact=True).first
            if await el.is_visible(timeout=3000):
                await el.click()
                await asyncio.sleep(0.5)
                return True
        except Exception:
            pass

        # Try contains-match via locator filter (handles "401 followers", "383 following")
        try:
            a = self.page.locator('a').filter(has_text=text).first
            if await a.is_visible(timeout=3000):
                await a.click()
                await asyncio.sleep(0.5)
                return True
        except Exception:
            pass

        # Try href containing text
        try:
            a = self.page.locator(f'a[href*="{text.lower()}"]').first
            if await a.is_visible(timeout=3000):
                await a.click()
                await asyncio.sleep(0.5)
                return True
        except Exception:
            pass
        return False

    async def _get_profile_info(self, username):
        await self._goto_with_retry(f"https://www.instagram.com/{username}/")
        html = await self.page.evaluate("document.body.innerHTML")
        info = {"user_id": None, "followers": None, "following": None}

        m = re.search(r'"user_id":"(\d+)"', html)
        if m: info["user_id"] = m.group(1)

        m = re.search(r'"edge_followed_by"\s*:\s*{\s*"count"\s*:\s*(\d+)', html)
        if m: info["followers"] = int(m.group(1))

        m = re.search(r'"edge_follow"\s*:\s*{\s*"count"\s*:\s*(\d+)', html)
        if m: info["following"] = int(m.group(1))

        try:
            js = """
            var info = {};
            var html = document.body.innerHTML;
            var m = html.match(/["']user_id["'][:"]+\\s*(\\d{8,})/);
            if(m) info.user_id = m[1];
            m = html.match(/["']pk["'][:"]+\\s*(\\d{8,})/);
            if(m) info.user_id = m[1];
            var scripts = document.querySelectorAll('script');
            for(var i = 0; i < scripts.length; i++) {
                var t = scripts[i].textContent || '';
                var m2 = t.match(/"user_id":"(\\d+)"/);
                if(m2) { info.user_id = m2[1]; break; }
            }
            var sections = document.querySelectorAll('section ul li span span');
            if(sections.length >= 2) {
                info.followers = parseInt(sections[0].textContent.replace(/,/g,''));
                info.following = parseInt(sections[1].textContent.replace(/,/g,''));
            }
            return JSON.stringify(Object.keys(info).length ? info : null);
            """
            extra = await self.page.evaluate(js)
            if extra and extra != "null":
                extra = json.loads(extra)
                if extra.get("user_id") and not info["user_id"]: info["user_id"] = extra["user_id"]
                if extra.get("followers") and not info["followers"]: info["followers"] = extra["followers"]
                if extra.get("following") and not info["following"]: info["following"] = extra["following"]
        except Exception:
            pass

        if not info["user_id"]:
            m = re.search(r'/(\d+)/', await self.page.evaluate("window.location.pathname"))
            if m: info["user_id"] = m.group(1)

        return info

    async def _api_followers(self, username):
        await self._goto_with_retry(f"https://www.instagram.com/{username}/")
        csrf = await self.page.evaluate('() => {var m = document.cookie.match(/csrftoken=([^;]+)/); return m ? m[1] : ""}')
        if not csrf:
            print("  API: No CSRF token")
            return None

        html = await self.page.evaluate("document.body.innerHTML")
        m = re.search(r'"user_id":"(\d+)"', html)
        if not m:
            print("  API: Could not resolve user ID")
            return None
        uid = m.group(1)

        all_users = []
        seen = set()
        max_id = None
        page_count = 0

        while True:
            page_count += 1
            params = f"page_size=50"
            if max_id:
                params += f"&max_id={max_id}"

            try:
                data = await self.page.evaluate(f"""async () => {{
                    var r = await fetch('/api/v1/friendships/{uid}/mutual_followers/?{params}', {{
                        headers: {{'X-CSRFToken': '{csrf}', 'X-IG-App-ID': '936619743392459', 'X-Requested-With': 'XMLHttpRequest'}}
                    }});
                    return await r.json();
                }}""")
            except Exception as e:
                print(f"  API followers page {page_count} error: {e}")
                if page_count >= 5:
                    return None
                await asyncio.sleep(2)
                continue

            users = data.get("users", [])
            new_count = 0
            for u in users:
                uname = u.get("username")
                if uname and uname not in seen:
                    seen.add(uname)
                    all_users.append(uname)
                    new_count += 1

            if page_count <= 2:
                print(f"  API followers page {page_count}: got {len(users)} entries ({new_count} new, total {len(all_users)})", end="")

            max_id = data.get("next_max_id")

            if not max_id:
                if page_count <= 2:
                    print(" — no more pages")
                break
            if len(users) < 50 and new_count == 0:
                if page_count <= 2:
                    print(" — last page")
                break

            await asyncio.sleep(jittered_delay(0.5, 1.5))

        if page_count > 2:
            print(f"  API followers done: {len(all_users)} unique users in {page_count} pages")
        return all_users

    async def _api_following(self, username):
        await self._goto_with_retry(f"https://www.instagram.com/{username}/")
        csrf = await self.page.evaluate('() => {var m = document.cookie.match(/csrftoken=([^;]+)/); return m ? m[1] : ""}')
        if not csrf:
            print("  API: No CSRF token")
            return None

        html = await self.page.evaluate("document.body.innerHTML")
        m = re.search(r'"user_id":"(\d+)"', html)
        if not m:
            print("  API: Could not resolve user ID")
            return None
        uid = m.group(1)

        all_users = []
        seen = set()
        max_id = None
        page_count = 0

        while True:
            page_count += 1
            params = f"count=50"
            if max_id:
                params += f"&max_id={max_id}"

            try:
                data = await self.page.evaluate(f"""async () => {{
                    var r = await fetch('/api/v1/friendships/{uid}/following/?{params}', {{
                        headers: {{'X-CSRFToken': '{csrf}', 'X-IG-App-ID': '936619743392459', 'X-Requested-With': 'XMLHttpRequest'}}
                    }});
                    return await r.json();
                }}""")
            except Exception as e:
                print(f"  API following page {page_count} error: {e}")
                if page_count >= 5:
                    return None
                await asyncio.sleep(2)
                continue

            users = data.get("users", [])
            new_count = 0
            for u in users:
                uname = u.get("username")
                if uname and uname not in seen:
                    seen.add(uname)
                    all_users.append(uname)
                    new_count += 1

            if page_count <= 2:
                print(f"  API following page {page_count}: got {len(users)} entries ({new_count} new, total {len(all_users)})", end="")

            max_id = data.get("next_max_id")

            if not max_id:
                if page_count <= 2:
                    print(" — no more pages")
                break
            if len(users) < 50 and new_count == 0:
                if page_count <= 2:
                    print(" — last page")
                break

            await asyncio.sleep(jittered_delay(0.5, 1.5))

        if page_count > 2:
            print(f"  API following done: {len(all_users)} unique users in {page_count} pages")
        return all_users

    _EXCLUDE = {'explore', 'reels', 'accounts', 'direct', 'stories'}

    async def _scrape_modal(self, max_items=200):
        usernames = []
        seen = set()
        stall_count = 0

        for it in range(1000):
            entries = await self.page.evaluate("""() => {
                var els = document.querySelectorAll('div[role="dialog"] a[role="link"]');
                return Array.from(els).map(e => e.getAttribute('href').replace(/^\\//,'').replace(/\\/.*$/,'')).filter(Boolean);
            }""")
            new = 0
            for u in entries:
                if u not in seen and u not in self._EXCLUDE:
                    seen.add(u)
                    usernames.append(u)
                    new += 1
            if new > 0:
                stall_count = 0
            else:
                stall_count += 1

            if stall_count >= 15:
                break
            if len(usernames) >= max_items:
                break

            # Check if this dialog shows "Suggested for you" (not real followers)
            has_suggestions = await self.page.evaluate("""() => {
                var d = document.querySelector('div[role="dialog"]');
                return d ? d.textContent.includes('Suggested for you') : false;
            }""")
            if has_suggestions and len(usernames) > 0:
                break

            await self.page.evaluate("""() => {
                var d = document.querySelector('div[role="dialog"]');
                if(!d) return;
                var all = d.querySelectorAll('div');
                for(var el of all) {
                    var cs = window.getComputedStyle(el);
                    if((cs.overflowY === 'scroll' || cs.overflowY === 'auto') && el.scrollHeight > el.clientHeight) {
                        el.scrollTop += el.clientHeight * 0.85;
                        el.dispatchEvent(new Event('scroll', {bubbles: true}));
                    }
                }
            }""")
            await asyncio.sleep(jittered_delay(0.7, 1.8))

        return usernames

    async def _page_followers(self, username):
        try:
            await self._goto_with_retry(f"https://www.instagram.com/{username}/")
            await self.page.wait_for_timeout(3000)
            if not await self._click_text("followers"):
                print("  _page_followers: cannot find followers text")
                return None
            result = await self._scrape_modal(max_items=100)
            if result is None:
                print("  _page_followers: _scrape_modal returned None")
            return result
        except Exception as e:
            print(f"  _page_followers error: {e}")
        return None

    async def _page_following(self, username):
        try:
            await self._goto_with_retry(f"https://www.instagram.com/{username}/")
            await self.page.wait_for_timeout(3000)
            if not await self._click_text("following"):
                print("  _page_following: cannot find following text")
                return None
            result = await self._scrape_modal(max_items=500)
            if result is None:
                print("  _page_following: _scrape_modal returned None")
            return result
        except Exception as e:
            print(f"  _page_following error: {e}")
        return None

    async def get_followers(self, username):
        return await self._page_followers(username)

    async def get_following(self, username):
        return await self._page_following(username)

    async def get_profile_pic(self, username):
        if "instagram.com" not in self.page.url:
            try:
                await self.page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=self.timeout)
                await self.page.wait_for_timeout(2000)
            except Exception:
                pass

        await self.rate_limiter.acquire()
        await self.budget.spend()
        url_data = await self.page.evaluate(f"""async () => {{
            try {{
                var csrf = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1];
                if(!csrf) return null;
                var r = await fetch('/api/v1/users/web_profile_info/?username={username}', {{
                    headers: {{'X-CSRFToken': csrf, 'X-IG-App-ID': '936619743392459'}}
                }});
                if(!r.ok) return null;
                var data = await r.json();
                if(data && data.data && data.data.user) {{
                    var u = data.data.user;
                    return u.hd_profile_pic_url_info ? u.hd_profile_pic_url_info.url : u.profile_pic_url;
                }}
                return null;
            }} catch(e) {{ return null; }}
        }}""")
        if not url_data:
            return None, None

        resp = await self.page.request.get(url_data)
        kind = detect_soft_block(resp.status, url_data, "")
        if kind:
            raise SoftBlockError(kind, "profile_pic")
        if resp.ok:
            return url_data, await resp.body()
        return url_data, None
