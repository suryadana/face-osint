"""
Instagram scraper — Playwright-based, no API needed.
"""
import json, time, re, random
from playwright.sync_api import sync_playwright

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

def _backoff_wait(attempt):
    delay = min(2 ** attempt + random.uniform(0, 1), 30)
    print(f"  Rate limited, retrying in {delay:.0f}s (attempt {attempt+1})")
    time.sleep(delay)

class Instagram:
    def __init__(self, cookie_string, headless=True, timeout=15000):
        self.timeout = timeout
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch(headless=headless)
        self.ctx = self.browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        )
        self.ctx.add_cookies(parse_cookies(cookie_string))
        self.page = self.ctx.new_page()
        self._goto_with_retry("https://www.instagram.com/", "domcontentloaded")
        self.page.wait_for_timeout(2000)

    def _goto_with_retry(self, url, wait_until="domcontentloaded"):
        for attempt in range(5):
            try:
                r = self.page.goto(url, wait_until=wait_until, timeout=self.timeout)
                if r and r.status == 429:
                    _backoff_wait(attempt)
                    continue
                check = self.page.evaluate("() => document.body ? document.body.innerText.slice(0,200) : ''")
                if "rate limit" in check.lower() or "please wait" in check.lower():
                    _backoff_wait(attempt)
                    continue
                return r
            except Exception as e:
                if attempt < 4:
                    _backoff_wait(attempt)
                    continue
                raise e
        return None

    def get_profile_pic(self, username):
        """Download a user's profile picture via page navigation. Returns (url, bytes) or (None, None)."""
        url = self._get_pic_url(username)
        if not url: return None, None
        import requests
        try:
            r = requests.get(url, headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://www.instagram.com/"
            }, timeout=10)
            if r.status_code == 200: return url, r.content
        except: pass
        return None, None

    def _get_pic_url(self, username):
        try:
            self._goto_with_retry(f"https://www.instagram.com/{username}/")
            self.page.wait_for_timeout(1500)
            imgs = self.page.query_selector_all("img")
            for img in imgs:
                src = img.get_attribute("src")
                alt = img.get_attribute("alt") or ""
                if src and f"{username}'s profile picture" in alt and ".jpg" in src:
                    return src
            for img in imgs:
                src = img.get_attribute("src")
                alt = img.get_attribute("alt") or ""
                if src and "profile picture" in alt and ".jpg" in src and len(src) > 40:
                    return src
        except: pass
        return None

    def download_pic(self, url):
        import requests
        try:
            r = requests.get(url, headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://www.instagram.com/"
            }, timeout=10)
            if r.status_code == 200: return r.content
        except: pass
        return None

    def get_followers(self, username):
        """Fetch follower usernames via page scraping. Falls back to API."""
        result = self._page_followers(username)
        if result is not None:
            return result
        return self._api_followers(username)

    def get_following(self, username):
        """Fetch following usernames via page scraping. Falls back to API."""
        result = self._page_following(username)
        if result is not None:
            return result
        return self._api_following(username)

    def _get_profile_info(self, username):
        try:
            self._goto_with_retry(f"https://www.instagram.com/{username}/")
            self.page.wait_for_timeout(2000)
            result = self.page.evaluate("""
() => {
    var info = {user_id: '', followers: 0, following: 0};
    var html = document.documentElement.innerHTML;

    var m = html.match(/["']user_id["'][:"]+\\s*(\\d{8,})/);
    if(m) info.user_id = m[1];
    m = html.match(/["']pk["'][:"]+\\s*(\\d{8,})/);
    if(m) info.user_id = m[1];

    var scripts = document.querySelectorAll('script');
    for(var i = 0; i < scripts.length; i++) {
        var t = scripts[i].textContent || '';
        var m2 = t.match(/"user_id":"(\\d+)"/);
        if(m2) { info.user_id = m2[1]; break; }
        m2 = t.match(/"pk":"(\\d+)"/);
        if(m2) { info.user_id = m2[1]; break; }
    }

    var text = document.body.innerText;
    var fm = text.match(/(\\d+)\\s*follower/);
    if(fm) info.followers = parseInt(fm[1]);
    var fwm = text.match(/(\\d+)\\s*following/);
    if(fwm) info.following = parseInt(fwm[1]);

    return JSON.stringify(info);
}
""")
            return json.loads(result)
        except:
            return None

    def _api_followers(self, username):
        try:
            info = self._get_profile_info(username)
            if not info or not info.get('user_id'):
                return None
            uid = info['user_id']
            expected = info.get('followers', 0)
            all_users = []
            seen = set()
            max_id = None
            while True:
                url = f'https://www.instagram.com/api/v1/friendships/{uid}/followers/?count=200'
                if max_id:
                    url += f'&max_id={max_id}'
                js = f"""
async () => {{
    try {{
        var r = await fetch('{url}', {{
            credentials:'include',
            headers:{{'X-Requested-With':'XMLHttpRequest','X-IG-App-ID':'936619743392459','X-ASBD-ID':'359341'}}
        }});
        if(!r.ok) return JSON.stringify({{ok:false}});
        var d = await r.json();
        return JSON.stringify({{ok:true, users:(d.users||[]).map(function(u){{return u.username;}}), next_max_id:d.next_max_id||null}});
    }} catch(e) {{ return JSON.stringify({{ok:false}}); }}
}}
"""
                result = self.page.evaluate(js)
                data = json.loads(result)
                if not data.get("ok"):
                    break
                for u in data.get("users", []):
                    if u not in seen:
                        seen.add(u)
                        all_users.append(u)
                max_id = data.get("next_max_id")
                if not max_id or (expected > 0 and len(all_users) >= expected):
                    break
                self.page.wait_for_timeout(500)
            return all_users
        except Exception as e:
            print(f"  _api_followers error: {e}")
        return None

    def _api_following(self, username):
        try:
            info = self._get_profile_info(username)
            if not info or not info.get('user_id'):
                return None
            uid = info['user_id']
            expected = info.get('following', 0)
            all_users = []
            seen = set()
            max_id = None
            while True:
                url = f'https://www.instagram.com/api/v1/friendships/{uid}/following/?count=200'
                if max_id:
                    url += f'&max_id={max_id}'
                js = f"""
async () => {{
    try {{
        var r = await fetch('{url}', {{
            credentials:'include',
            headers:{{'X-Requested-With':'XMLHttpRequest','X-IG-App-ID':'936619743392459','X-ASBD-ID':'359341'}}
        }});
        if(!r.ok) return JSON.stringify({{ok:false}});
        var d = await r.json();
        return JSON.stringify({{ok:true, users:(d.users||[]).map(function(u){{return u.username;}}), next_max_id:d.next_max_id||null}});
    }} catch(e) {{ return JSON.stringify({{ok:false}}); }}
}}
"""
                result = self.page.evaluate(js)
                data = json.loads(result)
                if not data.get("ok"):
                    break
                for u in data.get("users", []):
                    if u not in seen:
                        seen.add(u)
                        all_users.append(u)
                max_id = data.get("next_max_id")
                if not max_id or (expected > 0 and len(all_users) >= expected):
                    break
                self.page.wait_for_timeout(500)
            return all_users
        except Exception as e:
            print(f"  _api_following error: {e}")
        return None

    def _click_text(self, text):
        """Click an element by visible text content."""
        try:
            el = self.page.query_selector(f"text={text}")
            if el:
                el.click()
                return True
        except: pass
        return False

    def _scrape_modal(self):
        """Scrape usernames from the open followers/following modal."""
        try:
            self.page.wait_for_timeout(2000)
            users = []
            seen = set()
            last_h = 0
            same_count = 0
            stall_threshold = 15

            for _ in range(1000):
                items = self.page.evaluate("""
                    Array.from(document.querySelectorAll('[role=dialog] a'))
                        .map(function(a) { return a.getAttribute('href'); })
                        .filter(function(h) { return h && h[0] === '/' && h.lastIndexOf('/') > 0; })
                        .map(function(h) { return h.replace(/^\\//, '').replace(/\\/$/, ''); })
                """)
                new_u = 0
                for u in items:
                    if u and u not in seen:
                        seen.add(u)
                        users.append(u)
                        new_u += 1

                self.page.evaluate("""
                    var d = document.querySelector('[role=dialog]');
                    if(d) {
                        var all = d.querySelectorAll('*');
                        for(var i = 0; i < all.length; i++) {
                            var cs = window.getComputedStyle(all[i]);
                            if(cs.overflowY === 'scroll') {
                                all[i].scroll(0, all[i].scrollTop + 400);
                                break;
                            }
                        }
                    }
                """)

                cur_h = self.page.evaluate("""
                    (function() {
                        var d = document.querySelector('[role=dialog]');
                        if(!d) return 0;
                        var all = d.querySelectorAll('*');
                        for(var i = 0; i < all.length; i++) {
                            var cs = window.getComputedStyle(all[i]);
                            if(cs.overflowY === 'scroll') return all[i].scrollHeight;
                        }
                        return 0;
                    })()
                """)

                if cur_h == last_h:
                    same_count += 1
                else:
                    same_count = 0
                    last_h = cur_h

                if same_count >= stall_threshold and new_u == 0:
                    break

                self.page.wait_for_timeout(600) if cur_h == last_h else self.page.wait_for_timeout(400)

            return users
        except Exception as e:
            print(f"  _scrape_modal error: {e}")
        return None

    def _page_followers(self, username):
        """Fallback: scrape followers from DOM modal."""
        try:
            self._goto_with_retry(f"https://www.instagram.com/{username}/")
            self.page.wait_for_timeout(3000)
            if not self._click_text("followers"):
                print("  _page_followers: cannot find followers text")
                return None
            result = self._scrape_modal()
            if result is None:
                print("  _page_followers: _scrape_modal returned None")
            return result
        except Exception as e:
            print(f"  _page_followers error: {e}")
        return None

    def _page_following(self, username):
        """Fallback: scrape following from DOM modal."""
        try:
            self._goto_with_retry(f"https://www.instagram.com/{username}/")
            self.page.wait_for_timeout(3000)
            if not self._click_text("following"):
                print("  _page_following: cannot find following text")
                return None
            result = self._scrape_modal()
            if result is None:
                print("  _page_following: _scrape_modal returned None")
            return result
        except Exception as e:
            print(f"  _page_following error: {e}")
        return None

    def close(self):
        try: self.browser.close()
        except: pass
        try: self.pw.stop()
        except: pass
