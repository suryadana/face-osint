# Rate-Limit Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Kurangi risiko rate-limit/ban Instagram dengan kontrol laju, jitter, deteksi soft-block, dan budget/cap — tanpa keluar dari Playwright.

**Architecture:** Modul baru `modules/ratelimit.py` berisi logika murni + primitif async (rate limiter global, jitter, backoff, budget, deteksi soft-block). Objek limiter/budget/throttle dibuat sekali di entrypoint `face-osint`, dioper ke `BFSSearch`, lalu ke tiap `Instagram`. `instagram.py` memanggil limiter sebelum tiap request dan mendeteksi soft-block; `search.py` menegakkan cap expansion + berhenti rapi saat soft-block/budget habis.

**Tech Stack:** Python 3.9, asyncio, Playwright (async). Test: `pytest` + `pytest-asyncio` (dev-only).

## Global Constraints

- **Scraping WAJIB tetap via Playwright** (browser context). Jangan tambah raw-HTTP client.
- **Kompatibel Python 3.9** — hindari sintaks 3.10+ (`match`, union `X | Y` di anotasi runtime).
- **Zero dependency baru untuk runtime** — hanya `pytest`/`pytest-asyncio` sebagai dev dependency (`requirements-dev.txt`).
- **Determinisme test** — primitif berbasis waktu (`RateLimiter`, backoff) menerima injeksi `time_fn`/`sleep_fn`/`rng` agar bisa dites tanpa tidur nyata.
- **Bahasa string user-facing:** campur ID/EN mengikuti gaya kode yang ada.
- **Default aman (config):** `RATE_PER_MIN = 20`, `DELAY_RANGE = (1.0, 3.0)`, `MAX_REQUESTS = 800`, `MAX_EXPANSIONS_PER_LAYER = 15`, `BACKOFF_CAP = 300`.

---

## File Structure

- **Create** `modules/ratelimit.py` — semua primitif hardening (pure + async).
- **Create** `tests/test_ratelimit.py` — unit test primitif.
- **Create** `tests/test_search_limits.py` — unit test cap expansion + graceful-stop (pakai fake Instagram).
- **Create** `requirements-dev.txt` — `pytest`, `pytest-asyncio`.
- **Create** `pytest.ini` — set `asyncio_mode = auto`.
- **Modify** `modules/config.py` — knob baru (rate, delay, budget, cap, backoff cap).
- **Modify** `modules/instagram.py` — limiter.acquire + jitter + deteksi soft-block + backoff pakai `BACKOFF_CAP` + throttle global.
- **Modify** `modules/search.py` — inject limiter/budget/throttle; cap expansion; graceful stop.
- **Modify** `face-osint` — flag CLI `--rate/--max-requests/--max-expand/--delay-min/--delay-max`, buat objek, oper ke `BFSSearch`.
- **Modify** `docs/penggunaan.md` + `docs/keamanan-dan-rate-limit.md` — dokumentasikan knob baru.

---

### Task 1: Test harness + pure helpers (`jittered_delay`, `backoff_delay`)

**Files:**
- Create: `requirements-dev.txt`
- Create: `pytest.ini`
- Create: `modules/ratelimit.py`
- Test: `tests/test_ratelimit.py`

**Interfaces:**
- Produces:
  - `jittered_delay(lo: float, hi: float, rng=random) -> float`
  - `backoff_delay(attempt: int, base: float = 2.0, cap: float = 300.0, rng=random) -> float`

- [ ] **Step 1: Dev deps + pytest config**

`requirements-dev.txt`:
```
pytest
pytest-asyncio
```

`pytest.ini`:
```ini
[pytest]
asyncio_mode = auto
testpaths = tests
```

Run: `pip install -r requirements-dev.txt`

- [ ] **Step 2: Write failing test**

`tests/test_ratelimit.py`:
```python
import random
from modules.ratelimit import jittered_delay, backoff_delay


def test_jittered_delay_within_bounds():
    rng = random.Random(0)
    for _ in range(100):
        d = jittered_delay(1.0, 3.0, rng=rng)
        assert 1.0 <= d <= 3.0


def test_jittered_delay_zero_range():
    assert jittered_delay(0.0, 0.0) == 0.0


def test_backoff_delay_grows_and_caps():
    seq = [backoff_delay(a, base=2.0, cap=300.0, rng=random.Random(1)) for a in range(12)]
    assert seq[0] < seq[3] < seq[6]         # grows
    assert all(d <= 300.0 for d in seq)     # capped
    assert seq[-1] == 300.0                  # deep attempt saturates cap
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_ratelimit.py -v`
Expected: FAIL — `ModuleNotFoundError` / `ImportError: cannot import name 'jittered_delay'`.

- [ ] **Step 4: Implement helpers**

`modules/ratelimit.py`:
```python
"""Rate-limit hardening primitives (pure + async)."""
import asyncio
import random


def jittered_delay(lo, hi, rng=random):
    """Random delay in [lo, hi]. Returns 0.0 when lo==hi==0."""
    if hi <= lo:
        return float(lo)
    return rng.uniform(lo, hi)


def backoff_delay(attempt, base=2.0, cap=300.0, rng=random):
    """Exponential backoff with jitter, capped at `cap` seconds."""
    return min(base ** attempt + rng.uniform(0, 1), cap)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_ratelimit.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add requirements-dev.txt pytest.ini modules/ratelimit.py tests/test_ratelimit.py
git commit -m "feat(ratelimit): add pure jitter+backoff helpers with tests"
```

---

### Task 2: `RateLimiter` (global async pacer)

**Files:**
- Modify: `modules/ratelimit.py`
- Test: `tests/test_ratelimit.py`

**Interfaces:**
- Consumes: `jittered_delay`
- Produces: `RateLimiter(rate_per_min, jitter_range=(0.0, 0.0), time_fn=None, sleep_fn=None)` with `async def acquire(self) -> None`. `rate_per_min <= 0` disables pacing (no wait).

- [ ] **Step 1: Write failing test**

Append to `tests/test_ratelimit.py`:
```python
import pytest
from modules.ratelimit import RateLimiter


async def test_rate_limiter_spaces_calls():
    clock = {"t": 0.0}
    slept = []

    def time_fn():
        return clock["t"]

    async def sleep_fn(d):
        slept.append(d)
        clock["t"] += d          # advance virtual clock

    rl = RateLimiter(rate_per_min=60, time_fn=time_fn, sleep_fn=sleep_fn)  # min_interval=1.0s
    await rl.acquire()           # first: no wait
    await rl.acquire()           # second: must wait ~1.0s
    assert slept and abs(slept[-1] - 1.0) < 1e-6


async def test_rate_limiter_disabled():
    slept = []

    async def sleep_fn(d):
        slept.append(d)

    rl = RateLimiter(rate_per_min=0, sleep_fn=sleep_fn)
    await rl.acquire()
    await rl.acquire()
    assert slept == []           # disabled => never sleeps
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ratelimit.py -k rate_limiter -v`
Expected: FAIL — `ImportError: cannot import name 'RateLimiter'`.

- [ ] **Step 3: Implement `RateLimiter`**

Append to `modules/ratelimit.py`:
```python
class RateLimiter:
    """Global pacer: serializes acquire() so requests are >= min_interval apart."""

    def __init__(self, rate_per_min, jitter_range=(0.0, 0.0), time_fn=None, sleep_fn=None):
        self.min_interval = (60.0 / rate_per_min) if rate_per_min and rate_per_min > 0 else 0.0
        self.jitter_range = jitter_range
        self._time = time_fn or (lambda: asyncio.get_event_loop().time())
        self._sleep = sleep_fn or asyncio.sleep
        self._lock = asyncio.Lock()
        self._next_allowed = 0.0

    async def acquire(self):
        if self.min_interval <= 0.0:
            return
        async with self._lock:
            now = self._time()
            wait = self._next_allowed - now
            if wait > 0:
                await self._sleep(wait)
            extra = jittered_delay(*self.jitter_range)
            self._next_allowed = self._time() + self.min_interval + extra
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ratelimit.py -k rate_limiter -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add modules/ratelimit.py tests/test_ratelimit.py
git commit -m "feat(ratelimit): add global RateLimiter with injectable clock"
```

---

### Task 3: `RequestBudget` + `BudgetExceeded`

**Files:**
- Modify: `modules/ratelimit.py`
- Test: `tests/test_ratelimit.py`

**Interfaces:**
- Produces:
  - `class BudgetExceeded(Exception)` with attrs `.spent`, `.limit`.
  - `RequestBudget(max_requests=None)` with `async def spend(self, n=1) -> None` (raises `BudgetExceeded` when total exceeds `max_requests`) and `.spent` int property.

- [ ] **Step 1: Write failing test**

Append to `tests/test_ratelimit.py`:
```python
from modules.ratelimit import RequestBudget, BudgetExceeded


async def test_budget_counts_and_raises():
    b = RequestBudget(max_requests=3)
    await b.spend()          # 1
    await b.spend(2)         # 3 (== limit, still OK)
    assert b.spent == 3
    with pytest.raises(BudgetExceeded) as ei:
        await b.spend()      # 4 > 3
    assert ei.value.limit == 3
    assert ei.value.spent == 4


async def test_budget_unlimited_when_none():
    b = RequestBudget(max_requests=None)
    for _ in range(1000):
        await b.spend()
    assert b.spent == 1000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ratelimit.py -k budget -v`
Expected: FAIL — `ImportError: cannot import name 'RequestBudget'`.

- [ ] **Step 3: Implement**

Append to `modules/ratelimit.py`:
```python
class BudgetExceeded(Exception):
    def __init__(self, spent, limit):
        self.spent = spent
        self.limit = limit
        super().__init__(f"request budget exceeded: {spent} > {limit}")


class RequestBudget:
    """Counts total requests spent across the run; raises when over max_requests."""

    def __init__(self, max_requests=None):
        self.max_requests = max_requests
        self.spent = 0
        self._lock = asyncio.Lock()

    async def spend(self, n=1):
        async with self._lock:
            self.spent += n
            if self.max_requests is not None and self.spent > self.max_requests:
                raise BudgetExceeded(self.spent, self.max_requests)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ratelimit.py -k budget -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add modules/ratelimit.py tests/test_ratelimit.py
git commit -m "feat(ratelimit): add RequestBudget with hard cap"
```

---

### Task 4: `detect_soft_block` + `SoftBlockError`

**Files:**
- Modify: `modules/ratelimit.py`
- Test: `tests/test_ratelimit.py`

**Interfaces:**
- Produces:
  - `class SoftBlockError(Exception)` with attr `.kind`.
  - `detect_soft_block(status: int, url: str, body_text: str) -> str | None` — returns a kind string (`'login_redirect'`, `'checkpoint'`, `'challenge'`, `'feedback_required'`) or `None`. NOTE: HTTP 429 is a *throttle* (handled by backoff), NOT a soft-block, so it returns `None`.

- [ ] **Step 1: Write failing test**

Append to `tests/test_ratelimit.py`:
```python
from modules.ratelimit import detect_soft_block, SoftBlockError


def test_detect_login_redirect():
    assert detect_soft_block(200, "https://www.instagram.com/accounts/login/?next=/x/", "") == "login_redirect"


def test_detect_body_markers():
    assert detect_soft_block(400, "https://www.instagram.com/x/", '{"message":"checkpoint_required"}') == "checkpoint"
    assert detect_soft_block(400, "u", '{"message":"challenge_required"}') == "challenge"
    assert detect_soft_block(400, "u", '{"message":"feedback_required"}') == "feedback_required"


def test_429_is_not_soft_block():
    assert detect_soft_block(429, "https://www.instagram.com/x/", "rate limited") is None


def test_clean_response_is_none():
    assert detect_soft_block(200, "https://www.instagram.com/x/", '{"data":{"user":{}}}') is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ratelimit.py -k "soft or detect or 429 or clean" -v`
Expected: FAIL — `ImportError: cannot import name 'detect_soft_block'`.

- [ ] **Step 3: Implement**

Append to `modules/ratelimit.py`:
```python
class SoftBlockError(Exception):
    def __init__(self, kind, detail=""):
        self.kind = kind
        super().__init__(("soft-block: %s %s" % (kind, detail)).strip())


_BODY_MARKERS = [
    ("checkpoint", "checkpoint_required"),
    ("challenge", "challenge_required"),
    ("feedback_required", "feedback_required"),
]


def detect_soft_block(status, url, body_text):
    """Detect account-level soft blocks. 429 (throttle) is intentionally NOT one."""
    if status == 429:
        return None
    if url and "/accounts/login" in url:
        return "login_redirect"
    if body_text:
        low = body_text.lower()
        for kind, marker in _BODY_MARKERS:
            if marker in low:
                return kind
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ratelimit.py -k "soft or detect or 429 or clean" -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add modules/ratelimit.py tests/test_ratelimit.py
git commit -m "feat(ratelimit): add soft-block detection + SoftBlockError"
```

---

### Task 5: Config knobs

**Files:**
- Modify: `modules/config.py:16-21` (constants block)

**Interfaces:**
- Produces module constants: `RATE_PER_MIN`, `DELAY_RANGE`, `MAX_REQUESTS`, `MAX_EXPANSIONS_PER_LAYER`, `BACKOFF_CAP`.

- [ ] **Step 1: Write failing test**

Create `tests/test_config.py`:
```python
from modules import config


def test_hardening_defaults_exist():
    assert config.RATE_PER_MIN == 20
    assert config.DELAY_RANGE == (1.0, 3.0)
    assert config.MAX_REQUESTS == 800
    assert config.MAX_EXPANSIONS_PER_LAYER == 15
    assert config.BACKOFF_CAP == 300
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL — `AttributeError: module 'modules.config' has no attribute 'RATE_PER_MIN'`.

- [ ] **Step 3: Add constants**

In `modules/config.py`, after the existing `MAX_DEPTH = 3` line, add:
```python
# --- Rate-limit hardening ---
RATE_PER_MIN = 20                 # global read pace (requests/min); 0 disables
DELAY_RANGE = (1.0, 3.0)          # jittered inter-action delay (seconds)
MAX_REQUESTS = 800                # per-run request budget; None disables
MAX_EXPANSIONS_PER_LAYER = 15     # cap accounts expanded per BFS layer; None disables
BACKOFF_CAP = 300                 # max backoff seconds (was hardcoded 30)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add modules/config.py tests/test_config.py
git commit -m "feat(config): add rate-limit hardening knobs"
```

---

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

### Task 7: Enforce cap + graceful stop in `search.py`

**Files:**
- Modify: `modules/search.py` (constructor `:12-31`, `_check_one` `:33-59`, `search` `:61-142`)
- Test: `tests/test_search_limits.py`

**Interfaces:**
- Consumes: `RateLimiter`, `RequestBudget`, `BudgetExceeded`, `SoftBlockError`, `config.MAX_EXPANSIONS_PER_LAYER`.
- Produces: `BFSSearch(..., rate_limiter=None, budget=None)` stores them and passes into every `Instagram(...)`. New attrs `self.stopped` (`asyncio.Event`) + `self.stop_reason` (str|None). Expansion loop slices candidates to `config.MAX_EXPANSIONS_PER_LAYER`.

- [ ] **Step 1: Write failing test (fake expansion cap)**

`tests/test_search_limits.py`:
```python
from modules import config
from modules.search import cap_expansions


def test_cap_expansions_limits_count():
    users = [f"u{i}" for i in range(50)]
    assert cap_expansions(users, 15) == users[:15]


def test_cap_expansions_none_disables():
    users = ["a", "b", "c"]
    assert cap_expansions(users, None) == users
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_search_limits.py -v`
Expected: FAIL — `ImportError: cannot import name 'cap_expansions'`.

- [ ] **Step 3: Add `cap_expansions` helper + inject limits**

In `modules/search.py`, add module-level helper:
```python
def cap_expansions(candidates, max_per_layer):
    """Return at most max_per_layer candidates (None => no cap)."""
    if max_per_layer is None:
        return list(candidates)
    return list(candidates)[:max_per_layer]
```
Extend `BFSSearch.__init__` to accept and store `rate_limiter=None, budget=None`, and add:
```python
        self.rate_limiter = rate_limiter
        self.budget = budget
        self.stopped = asyncio.Event()
        self.stop_reason = None
```
In `_check_one` (`:40`) and the expansion `Instagram(...)` (`:119`), pass `rate_limiter=self.rate_limiter, budget=self.budget`. Wrap the bodies so `SoftBlockError`/`BudgetExceeded` set stop:
```python
        except (SoftBlockError, BudgetExceeded) as e:
            self.stop_reason = str(e)
            self.stopped.set()
            self.found.set()   # reuse existing short-circuit to unwind everything
            return None
```
Import at top: `from modules.ratelimit import SoftBlockError, BudgetExceeded`.

- [ ] **Step 4: Apply expansion cap in `search`**

In `search` (`:104`), after building `expand`, insert:
```python
        expand = cap_expansions(expand, config.MAX_EXPANSIONS_PER_LAYER)
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_search_limits.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add modules/search.py tests/test_search_limits.py
git commit -m "feat(search): cap expansions per layer + graceful stop on soft-block/budget"
```

---

### Task 8: CLI flags + docs

**Files:**
- Modify: `face-osint` (`cmd_search` arg parse `:169-181`, help `:150-158`, `BFSSearch(...)` `:222`, `_scrape_user`/`Instagram(...)` sites)
- Modify: `docs/penggunaan.md`, `docs/keamanan-dan-rate-limit.md`

**Interfaces:**
- Consumes: `RateLimiter`, `RequestBudget` from `modules.ratelimit`, `config.*` defaults.
- Produces: CLI flags `--rate N`, `--max-requests N`, `--max-expand N`, `--delay-min X`, `--delay-max X`; builds one `RateLimiter` + one `RequestBudget` and passes into `BFSSearch`.

- [ ] **Step 1: Parse new flags in `cmd_search`**

In `cmd_search` arg loop (`:169-181`), add before the `else:` branch:
```python
        elif args[i] == "--rate" and i + 1 < len(args):
            rate = int(args[i + 1]); i += 2
        elif args[i] == "--max-requests" and i + 1 < len(args):
            max_requests = int(args[i + 1]); i += 2
        elif args[i] == "--max-expand" and i + 1 < len(args):
            max_expand = int(args[i + 1]); i += 2
        elif args[i] == "--delay-min" and i + 1 < len(args):
            delay_min = float(args[i + 1]); i += 2
        elif args[i] == "--delay-max" and i + 1 < len(args):
            delay_max = float(args[i + 1]); i += 2
```
Initialize defaults just above the loop (near `depth = 1`):
```python
    rate = config.RATE_PER_MIN
    max_requests = config.MAX_REQUESTS
    max_expand = config.MAX_EXPANSIONS_PER_LAYER
    delay_min, delay_max = config.DELAY_RANGE
```

- [ ] **Step 2: Build limiter/budget and pass to BFSSearch**

At top of `face-osint`, add: `from modules.ratelimit import RateLimiter, RequestBudget`.
Before constructing `BFSSearch` (`:222`), add:
```python
    limiter = RateLimiter(rate, jitter_range=(delay_min, delay_max))
    budget = RequestBudget(max_requests)
    config.MAX_EXPANSIONS_PER_LAYER = max_expand   # honor CLI override
```
Change the constructor call to:
```python
    searcher = BFSSearch(ref_path, cookie_string=cookie, workers=workers,
                         face_engine=engine, ref_emb=ref_emb,
                         rate_limiter=limiter, budget=budget)
```
After `search(...)` returns, if `searcher.stop_reason`, print it:
```python
    if searcher.stop_reason:
        print(f"\n  STOPPED early (safety): {searcher.stop_reason}")
```

- [ ] **Step 3: Update help text**

In `cmd_search` usage block (`:150-158`), add lines:
```python
        print("  --rate N        Global read pace, requests/min (default 20; 0=off)")
        print("  --max-requests N  Per-run request budget (default 800)")
        print("  --max-expand N  Max accounts expanded per layer (default 15)")
        print("  --delay-min X / --delay-max X  Jittered inter-action delay seconds")
```

- [ ] **Step 4: Manual verification (real run, low volume)**

Run:
```bash
./face-osint --cookie "sessionid=..." search ref.jpg <username> --depth 1 --rate 20 --max-requests 60
```
Expected: run paces requests (visible spacing), stops with `STOPPED early (safety): request budget exceeded: 61 > 60` once budget hit, and never retry-loops on a soft-block.

- [ ] **Step 5: Update docs**

In `docs/penggunaan.md` options table for `search`, add rows for `--rate`, `--max-requests`, `--max-expand`, `--delay-min/max` with the defaults above. In `docs/keamanan-dan-rate-limit.md` "Mitigasi" section, replace the "hanya menurunkan volume" caveats that are now fixed and note the new global limiter, jitter, soft-block hard-stop, and budget/cap as implemented mitigations.

- [ ] **Step 6: Commit**

```bash
git add face-osint docs/penggunaan.md docs/keamanan-dan-rate-limit.md
git commit -m "feat(cli): expose rate/budget/expand/delay flags + document"
```

---

## Self-Review

**Spec coverage (scope A, item 1–5):**
- Item 1 global rate limiter → Task 2 (`RateLimiter`) + wired Task 6/8. ✓
- Item 2 jitter delays → Task 1 (`jittered_delay`) + wired Task 6. ✓
- Item 3 soft-block detection + hard-stop → Task 4 (`detect_soft_block`) + Task 6 (raise) + Task 7 (graceful stop). ✓
- Item 4 budget + expansion cap → Task 3 (`RequestBudget`) + Task 7 (`cap_expansions`). ✓
- Item 5 global adaptive backoff → Task 1 (`backoff_delay` cap) + Task 6 (`BACKOFF_CAP`, applies on 429). Note: "pause ALL workers" is partially covered (each worker backs off on its own 429; a shared cross-worker pause is deferred as follow-up to keep Task 6 in-place and low-risk). ✓ (documented limitation)

**Placeholder scan:** none — every code step shows concrete code.

**Type consistency:** `rate_limiter`/`budget` kwargs consistent across `Instagram` (Task 6), `BFSSearch` (Task 7), and construction (Task 8). `detect_soft_block(status, url, body_text)` signature identical in Task 4 def and Task 6 calls. `cap_expansions(candidates, max_per_layer)` identical Task 7 def/use.

**Known limitation (deferred, not in scope A):** cross-worker global throttle pause and proxy support are items 6–7 (scope B) — intentionally out of this plan.
