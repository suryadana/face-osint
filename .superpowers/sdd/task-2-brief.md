### Task 2: `parse_profile_media` + fetch/download (instagram.py)

**Files:**
- Modify: `modules/instagram.py`
- Test: `tests/test_profile_media.py`

**Interfaces:**
- Consumes: `RateLimiter`/`RequestBudget` already wired on `Instagram` (from hardening branch).
- Produces:
  - `parse_profile_media(api_json) -> dict` — pure; returns `{"profile_pic_url": str|None, "post_urls": [str, ...]}`.
  - `Instagram.get_profile_media(username) -> dict` — one `web_profile_info` fetch, returns `parse_profile_media(...)`.
  - `Instagram.download_image(url) -> bytes | None` — via `page.request.get`, paced by the limiter/budget.

- [ ] **Step 1: Write failing test**

`tests/test_profile_media.py`:
```python
from modules.instagram import parse_profile_media


def _api(user):
    return {"data": {"user": user}}


def test_parse_extracts_pic_and_posts():
    user = {
        "hd_profile_pic_url_info": {"url": "https://cdn/hd.jpg"},
        "profile_pic_url": "https://cdn/lo.jpg",
        "edge_owner_to_timeline_media": {"edges": [
            {"node": {"display_url": "https://cdn/p1.jpg"}},
            {"node": {"display_url": "https://cdn/p2.jpg"}},
        ]},
    }
    out = parse_profile_media(_api(user))
    assert out["profile_pic_url"] == "https://cdn/hd.jpg"      # hd preferred
    assert out["post_urls"] == ["https://cdn/p1.jpg", "https://cdn/p2.jpg"]


def test_parse_falls_back_to_lo_pic_and_empty_posts():
    out = parse_profile_media(_api({"profile_pic_url": "https://cdn/lo.jpg"}))
    assert out["profile_pic_url"] == "https://cdn/lo.jpg"
    assert out["post_urls"] == []


def test_parse_handles_missing_user():
    out = parse_profile_media({"data": {}})
    assert out == {"profile_pic_url": None, "post_urls": []}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_profile_media.py -v`
Expected: FAIL — `ImportError: cannot import name 'parse_profile_media'`.

- [ ] **Step 3: Implement pure parser**

In `modules/instagram.py`, add module-level function:
```python
def parse_profile_media(api_json):
    """Extract profile pic URL + recent post image URLs from a web_profile_info response."""
    user = ((api_json or {}).get("data") or {}).get("user") or {}
    pic = (user.get("hd_profile_pic_url_info") or {}).get("url") or user.get("profile_pic_url")
    edges = (user.get("edge_owner_to_timeline_media") or {}).get("edges") or []
    posts = []
    for e in edges:
        node = e.get("node") or {}
        u = node.get("display_url") or node.get("thumbnail_src")
        if u:
            posts.append(u)
    return {"profile_pic_url": pic, "post_urls": posts}
```

- [ ] **Step 4: Add `get_profile_media` + `download_image` methods**

Add to the `Instagram` class (model on existing `get_profile_pic` `:396-426`, but return the parsed JSON). The in-page fetch must return the whole `data` object, not just the url:
```python
    async def get_profile_media(self, username):
        if "instagram.com" not in self.page.url:
            try:
                await self.page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=self.timeout)
                await self.page.wait_for_timeout(2000)
            except Exception:
                pass
        raw = await self.page.evaluate(f"""async () => {{
            try {{
                var csrf = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1];
                if(!csrf) return null;
                var r = await fetch('/api/v1/users/web_profile_info/?username={username}', {{
                    headers: {{'X-CSRFToken': csrf, 'X-IG-App-ID': '936619743392459'}}
                }});
                if(!r.ok) return null;
                return await r.json();
            }} catch(e) {{ return null; }}
        }}""")
        if not raw:
            return {"profile_pic_url": None, "post_urls": []}
        return parse_profile_media(raw)

    async def download_image(self, url):
        if not url:
            return None
        await self.rate_limiter.acquire()
        await self.budget.spend()
        resp = await self.page.request.get(url)
        return await resp.body() if resp.ok else None
```

- [ ] **Step 5: Run tests**

Run: `.venv/bin/pytest tests/test_profile_media.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add modules/instagram.py tests/test_profile_media.py
git commit -m "feat(instagram): parse profile+post media, add paced download_image (Playwright)"
```

---

