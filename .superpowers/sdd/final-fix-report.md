# Final whole-branch review fixes — rate-limit hardening

Branch: `feat/rate-limit-hardening`
Scope: apply FIX #1, #2, #4, #5, #6 from final review in one commit. #3 and #7 deferred (out of scope, noted below).

## FIX #1 (Important) — seed-scrape escapes governance

**Files/lines changed:** `face-osint`

- `_depth0_check` signature (`face-osint:113`) gained `rate_limiter=None, budget=None` params; its `Instagram(...)` construction (`face-osint:114`) now passes `rate_limiter=rate_limiter, budget=budget`.
- `_scrape_user` signature (`face-osint:127`) gained `rate_limiter=None, budget=None` params; its `Instagram(...)` construction (`face-osint:131`) now passes them through.
- In `cmd_search`, the `limiter = RateLimiter(...)` / `budget = RequestBudget(...)` / `config.MAX_EXPANSIONS_PER_LAYER = max_expand` block was moved from after the layer-0 scrape branch to immediately after the `print(f"  Depth: {depth}")` line (`face-osint:221-223`), i.e. before both the `depth == 0` branch and the cache/scrape branch.
- Call site for depth-0 (`face-osint:227`): `await _depth0_check(engine, ref_emb, username, cookie, threshold, limiter, budget)`.
- Call site for seed scrape (`face-osint:239`): `followers, following = await _scrape_user(username, cookie, limiter, budget)`.
- The later `BFSSearch(...)` construction (`face-osint:~251`) reuses the exact same `limiter`/`budget` instances — no second pair is constructed.

Net effect: every `Instagram(...)` construction reachable from `cmd_search` (depth-0 check, seed scrape, and all BFS expansions in `search.py`) now shares one `RateLimiter` + one `RequestBudget` for the whole run.

## FIX #2 (Important) — get_profile_pic home-nav ungoverned

**File/lines changed:** `modules/instagram.py:413-416` (`get_profile_pic`)

Before:
```python
if "instagram.com" not in self.page.url:
    try:
        await self.page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=self.timeout)
        await self.page.wait_for_timeout(2000)
    except Exception:
        pass
```

After:
```python
if "instagram.com" not in self.page.url:
    await self._goto_with_retry("https://www.instagram.com/")
    await self.page.wait_for_timeout(2000)
```

The bare `page.goto` (which bypassed pacing, budget accounting, and soft-block detection, and silently swallowed all exceptions) is replaced by `_goto_with_retry`, which already paces (`rate_limiter.acquire()`), counts against budget (`budget.spend()`), retries on transient errors/429 internally, and raises `SoftBlockError` on detected soft-block. The narrow `try/except: pass` was removed per the fix brief ("prefer routing through `_goto_with_retry` and letting SoftBlockError propagate") — `_goto_with_retry` already has its own internal retry/backoff loop, so the outer swallow was redundant and was hiding budget/soft-block signals from callers. `SoftBlockError`/`BudgetExceeded` raised here propagate up through `get_profile_pic` → `search._check_one`, which already catches `(SoftBlockError, BudgetExceeded)` and stops the search gracefully (`modules/search.py:72-76`). For the standalone `pic`/`scrape` commands (not through `search`), an uncaught `SoftBlockError` would propagate to `main()`/`asyncio.run` and surface as a traceback instead of being silently swallowed — this is an intentional behavior change per the fix brief (governance > silent pass), and is consistent with FIX #5's doc note that `pic`/`scrape` are not budget-governed but are still expected to fail loudly on a real soft-block rather than pretend nothing happened.

## FIX #4 (Minor) — stale -h help

**File/lines changed:** `face-osint:8-12` (module docstring)

Added four lines to the search options section of the top-of-file docstring (printed by `print(__doc__)` on `-h`/`--help`), matching the subcommand usage block verbatim:
```
    --rate N        Global read pace, requests/min (default 20; 0=off)
    --max-requests N  Per-run request budget (default 800)
    --max-expand N  Max accounts expanded per layer (default 15)
    --delay-min X / --delay-max X  Jittered inter-action delay seconds
```

## FIX #5 (Minor) — doc scope note

**File/lines changed:** `docs/keamanan-dan-rate-limit.md`, end of "Mitigasi yang sudah ada" section (after the existing "Catatan: default ..." paragraph)

Added sentence (in Indonesian, matching surrounding style):
> Lingkup: limiter/budget/soft-block-stop di atas mengatur seluruh jalur perintah `search` (termasuk seed-scrape layer-0 dan `--depth 0`, sejak semuanya berbagi `limiter`/`budget` yang sama). Perintah `pic`/`scrape` yang dijalankan berdiri sendiri (di luar `search`) tetap tidak diatur budget/limiter — volumenya rendah (satu-dua request per invocation) sehingga dianggap di luar scope hardening ini.

Wording was adjusted from the brief's suggestion to reflect that FIX #1 now extends governance to `--depth 0` and the seed scrape (both are part of the `search` command path), while standalone `pic`/`scrape` invocations remain out of scope.

## FIX #6 (Minor) — dead import

**File/lines changed:** `modules/instagram.py:4`

Confirmed via `grep -n "random\." modules/instagram.py` (no matches) and `grep -n "random" modules/instagram.py` (only the import line) that `random` was never referenced. Changed:
```python
import json, re, random, asyncio
```
to:
```python
import json, re, asyncio
```
Post-fix grep for `random` in the file returns no matches (exit code 1).

## Deferred (explicitly out of scope per instructions)

- **#3**: `None`-response → 200 handling in `_goto_with_retry` — not touched (follow-up item, left as-is).
- **#7**: Duplicated stop-handler blocks in `search.py` (`_check_one`'s except clause vs. the expansion loop's except clause, both catching `(SoftBlockError, BudgetExceeded)` and setting `stop_reason`/`stopped`/`found`) — left untouched; they differ in control flow (one returns `None` from a coroutine, the other `break`s out of a `for` loop), so a shared helper would need care not to break either.

## Verification evidence

### 1. `.venv/bin/pytest tests/ -v` — full output (post-fix)

```
============================= test session starts ==============================
platform darwin -- Python 3.11.15, pytest-9.1.1, pluggy-1.6.0 -- /Users/suryadana/Learn/face-osint/.venv/bin/python3.11
cachedir: .pytest_cache
rootdir: /Users/suryadana/Learn/face-osint
configfile: pytest.ini
plugins: asyncio-1.4.0
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 16 items

tests/test_config.py::test_hardening_defaults_exist PASSED               [  6%]
tests/test_instagram_softblock.py::test_goto_raises_on_login_redirect PASSED [ 12%]
tests/test_instagram_softblock.py::test_goto_ok_returns_response PASSED  [ 18%]
tests/test_ratelimit.py::test_jittered_delay_within_bounds PASSED        [ 25%]
tests/test_ratelimit.py::test_jittered_delay_zero_range PASSED           [ 31%]
tests/test_ratelimit.py::test_backoff_delay_grows_and_caps PASSED        [ 37%]
tests/test_ratelimit.py::test_rate_limiter_spaces_calls PASSED           [ 43%]
tests/test_ratelimit.py::test_rate_limiter_disabled PASSED               [ 50%]
tests/test_ratelimit.py::test_budget_counts_and_raises PASSED            [ 56%]
tests/test_ratelimit.py::test_budget_unlimited_when_none PASSED          [ 62%]
tests/test_ratelimit.py::test_detect_login_redirect PASSED               [ 68%]
tests/test_ratelimit.py::test_detect_body_markers PASSED                 [ 75%]
tests/test_ratelimit.py::test_429_is_not_soft_block PASSED               [ 81%]
tests/test_ratelimit.py::test_clean_response_is_none PASSED              [ 87%]
tests/test_search_limits.py::test_cap_expansions_limits_count PASSED     [ 93%]
tests/test_search_limits.py::test_cap_expansions_none_disables PASSED    [100%]

============================== 16 passed in 0.40s ==============================
```

Baseline (before any edits) was also confirmed green at 16 passed, so no regressions.

### 2. CLI smoke tests

`.venv/bin/python3.11 face-osint search` (no args) — prints usage including the new flags, exit code 1 (expected, no-network):
```
Usage: face-osint search <ref_image> <instagram_username> [options]
Options:
  --depth N     Graph depth (0=user only, 1=followers/following, 2=their friends, ...)
  --workers N   Parallel workers (default 3)
  --threshold X Match threshold 0-1 (default 0.35)
  --no-cache    Re-scrape followers/following, ignore saved cache
  --rate N        Global read pace, requests/min (default 20; 0=off)
  --max-requests N  Per-run request budget (default 800)
  --max-expand N  Max accounts expanded per layer (default 15)
  --delay-min X / --delay-max X  Jittered inter-action delay seconds

Examples:
  face-osint search ref.jpg target_user --depth 1
  face-osint search ref.jpg target_user --depth 3 --workers 5
```

`.venv/bin/python3.11 face-osint -h` — module docstring now includes the new flags under `search`:
```
Commands:
  compare   <ref_image> <target_image>          Compare two face images
  search    <ref_image> <username> [options]    Recursive face-search through social graph
    --depth N    Graph depth (1=direct, 2=friends-of-friends, 3=...)
    --workers N  Parallel checks (default 3)
    --threshold X  Match threshold 0-1 (default 0.35)
    --rate N        Global read pace, requests/min (default 20; 0=off)
    --max-requests N  Per-run request budget (default 800)
    --max-expand N  Max accounts expanded per layer (default 15)
    --delay-min X / --delay-max X  Jittered inter-action delay seconds
  scrape    <username> [options]                Scrape followers/following lists
  pic       <username> [options]                Download profile picture
  list      <file>                              List results from a saved search
...
```

### 3. Sanity grep — no ungoverned `Instagram(...)` construction in the search path

```
$ grep -n "Instagram(" face-osint modules/search.py
face-osint:114:    async with Instagram(cookie, rate_limiter=rate_limiter, budget=budget) as ig:      # _depth0_check
face-osint:131:    async with Instagram(cookie, rate_limiter=rate_limiter, budget=budget) as ig:      # _scrape_user
face-osint:289:    async with Instagram(cookie) as ig:                                                # cmd_scrape (standalone, out of search path — expected)
face-osint:313:    async with Instagram(cookie) as ig:                                                # cmd_pic (standalone, out of search path — expected)
modules/search.py:54:  async with Instagram(self.cookie, ..., rate_limiter=self.rate_limiter, budget=self.budget) as ig:   # _check_one
modules/search.py:141: async with Instagram(self.cookie, ..., rate_limiter=self.rate_limiter, budget=self.budget) as ig:  # expansion loop
```

All four constructions reachable from `cmd_search` (`_depth0_check`, `_scrape_user`, and both `BFSSearch` sites in `search.py`) now pass `rate_limiter`/`budget`. The two remaining bare `Instagram(cookie)` calls are `cmd_scrape`/`cmd_pic`, standalone top-level commands not part of the `search` path — intentionally out of scope, consistent with the FIX #5 doc note.

### 6. Dead-import grep

```
$ grep -n "random" modules/instagram.py
(no output, exit code 1)
```

Confirms `random` import removed cleanly with no remaining references.

## Deferred items recap

- **#3** — `None`-response → 200 handling in `_goto_with_retry`: not touched, left for follow-up per instructions.
- **#7** — duplicated stop-handler blocks in `search.py`: not touched, left as-is per instructions (differ in control flow: coroutine-return vs. loop-break).
