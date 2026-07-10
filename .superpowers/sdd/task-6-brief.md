### Task 6: Wire limiter + jitter + soft-block into `instagram.py`

**Files:**
- Modify: `modules/instagram.py` (constructor `:51`, `_backoff_wait` `:45-48`, `_goto_with_retry` `:77-88`, fixed sleeps `:234,:302,:356`, `get_profile_pic` `:396-426`)
- Test: `tests/test_instagram_softblock.py`

**Interfaces:**
- Consumes: `RateLimiter`, `RequestBudget`, `detect_soft_block`, `SoftBlockError`, `backoff_delay`, `config.BACKOFF_CAP`, `config.DELAY_RANGE`.
- Produces: `Instagram(cookie_string, timeout=15000, skip_home=False, rate_limiter=None, budget=None)`. `_goto_with_retry` raises `SoftBlockError` on soft-block; calls `rate_limiter.acquire()` + `budget.spend()` before each navigation; uses `backoff_delay(attempt, cap=config.BACKOFF_CAP)`.

- [ ] **Step 1: Write failing test (fake page, no network)**

`tests/test_instagram_softblock.py`:
```python
import pytest
from modules.ratelimit import SoftBlockError, RateLimiter, RequestBudget
from modules.instagram import Instagram


class _FakeResp:
    def __init__(self, status):
        self.status = status


class _FakePage:
    def __init__(self, final_url, status=200):
        self.url = final_url
        self._status = status
    async def goto(self, url, wait_until="domcontentloaded", timeout=0):
        return _FakeResp(self._status)
    async def evaluate(self, *a, **k):
        return ""


async def test_goto_raises_on_login_redirect():
    ig = Instagram("sessionid=x", rate_limiter=RateLimiter(0), budget=RequestBudget())
    ig.page = _FakePage("https://www.instagram.com/accounts/login/?next=/y/")
    with pytest.raises(SoftBlockError) as ei:
        await ig._goto_with_retry("https://www.instagram.com/y/")
    assert ei.value.kind == "login_redirect"


async def test_goto_ok_returns_response():
    ig = Instagram("sessionid=x", rate_limiter=RateLimiter(0), budget=RequestBudget())
    ig.page = _FakePage("https://www.instagram.com/y/", status=200)
    r = await ig._goto_with_retry("https://www.instagram.com/y/")
    assert r.status == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_instagram_softblock.py -v`
Expected: FAIL — `Instagram.__init__() got an unexpected keyword argument 'rate_limiter'`.

- [ ] **Step 3: Add imports + constructor params**

At top of `modules/instagram.py` add:
```python
from modules import config
from modules.ratelimit import (
    RateLimiter, RequestBudget, backoff_delay,
    detect_soft_block, SoftBlockError, jittered_delay,
)
```
Replace the `__init__` signature (`:51`) and body head:
```python
    def __init__(self, cookie_string, timeout=15000, skip_home=False,
                 rate_limiter=None, budget=None):
        self.cookie_string = cookie_string
        self.timeout = timeout
        self.skip_home = skip_home
        self.rate_limiter = rate_limiter or RateLimiter(0)
        self.budget = budget or RequestBudget(None)
        self.ctx = None
        self.page = None
```

- [ ] **Step 4: Rewrite `_backoff_wait` to use configurable cap**

Replace `_backoff_wait` (`:45-48`):
```python
async def _backoff_wait(attempt):
    delay = backoff_delay(attempt, cap=config.BACKOFF_CAP)
    print(f"  Rate limited, retrying in {delay:.0f}s (attempt {attempt+1})", flush=True)
    await asyncio.sleep(delay)
```

- [ ] **Step 5: Rewrite `_goto_with_retry` — pace, budget, soft-block**

Replace `_goto_with_retry` (`:77-88`):
```python
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
```

- [ ] **Step 6: Replace fixed pagination/scroll sleeps with jitter**

- `:234` and `:302` (`await asyncio.sleep(0.5)` between API pages) → `await asyncio.sleep(jittered_delay(0.5, 1.5))`
- `:356` (`await asyncio.sleep(0.7)` between modal scrolls) → `await asyncio.sleep(jittered_delay(0.7, 1.8))`

- [ ] **Step 7: Soft-block check in `get_profile_pic`**

In `get_profile_pic` (`:396-426`), after `resp = await self.page.request.get(url_data)` (`:423`), before the `if resp.ok` check, add:
```python
            kind = detect_soft_block(resp.status, url_data, "")
            if kind:
                raise SoftBlockError(kind, "profile_pic")
```
And add `await self.rate_limiter.acquire()` + `await self.budget.spend()` immediately before the in-page `fetch` evaluate call (`:404`).

- [ ] **Step 8: Run tests**

Run: `pytest tests/test_instagram_softblock.py tests/test_ratelimit.py -v`
Expected: PASS (all).

- [ ] **Step 9: Commit**

```bash
git add modules/instagram.py tests/test_instagram_softblock.py
git commit -m "feat(instagram): pace requests, jitter delays, detect soft-blocks (Playwright)"
```

---

