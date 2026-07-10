# Task 6 Report: Wire limiter + jitter + soft-block into `instagram.py`

## Status: DONE

## What was implemented

Followed the brief's TDD steps in order, applying the exact code given verbatim.

1. **New test file** `tests/test_instagram_softblock.py` — two async tests using a
   fake `_FakePage` (no network, no browser): one asserts `_goto_with_retry` raises
   `SoftBlockError(kind="login_redirect")` when `page.url` ends up on
   `/accounts/login/`, the other asserts a normal 200 response is returned untouched.

2. **`modules/instagram.py` changes**:
   - Added imports: `from modules import config` and the six names from
     `modules.ratelimit` (`RateLimiter, RequestBudget, backoff_delay,
     detect_soft_block, SoftBlockError, jittered_delay`).
   - `Instagram.__init__` gained `rate_limiter=None, budget=None` params, defaulting
     to `RateLimiter(0)` (no-op pacing) and `RequestBudget(None)` (unlimited) when
     not supplied — so all existing call sites keep working unchanged.
   - `_backoff_wait` now calls `backoff_delay(attempt, cap=config.BACKOFF_CAP)`
     instead of the hardcoded `min(2**attempt + jitter, 30)`, and the print gained
     `flush=True`.
   - `_goto_with_retry` now calls `await self.rate_limiter.acquire()` and
     `await self.budget.spend()` before every navigation attempt (so budget is
     charged once per attempt, including retries), checks
     `detect_soft_block(status, final_url, "")` after each `goto` and raises
     `SoftBlockError` immediately (re-raised through the generic `except Exception`
     handler via an explicit `except SoftBlockError: raise` clause so it isn't
     swallowed/retried), and still falls back to `_backoff_wait` on 429 or
     transient exceptions.
   - Three fixed `asyncio.sleep(...)` calls jittered:
     - end of `_api_followers` pagination loop: `0.5` → `jittered_delay(0.5, 1.5)`
     - end of `_api_following` pagination loop: `0.5` → `jittered_delay(0.5, 1.5)`
     - end of `_scrape_modal` scroll loop: `0.7` → `jittered_delay(0.7, 1.8)`
     (Left the three unrelated `asyncio.sleep(0.5)` calls inside `_click_text`
     untouched — brief only names the API-pagination and modal-scroll sleeps.)
   - `get_profile_pic`: added `await self.rate_limiter.acquire()` +
     `await self.budget.spend()` immediately before the in-page `fetch` evaluate
     call, and after `resp = await self.page.request.get(url_data)` added a
     `detect_soft_block(resp.status, url_data, "")` check that raises
     `SoftBlockError(kind, "profile_pic")` before the existing `if resp.ok` check.

No other files were touched. `BudgetExceeded`/`RequestBudget` semantics, `RateLimiter`
semantics, and `detect_soft_block` signature were consumed as-is from the already-committed
`modules/ratelimit.py` — no changes made there.

## TDD evidence

### RED (Step 2)

```
$ .venv/bin/pytest tests/test_instagram_softblock.py -v
```
```
collected 2 items

tests/test_instagram_softblock.py::test_goto_raises_on_login_redirect FAILED [ 50%]
tests/test_instagram_softblock.py::test_goto_ok_returns_response FAILED [100%]

=================================== FAILURES ===================================
______________________ test_goto_raises_on_login_redirect ______________________
    ig = Instagram("sessionid=x", rate_limiter=RateLimiter(0), budget=RequestBudget())
E   TypeError: Instagram.__init__() got an unexpected keyword argument 'rate_limiter'
________________________ test_goto_ok_returns_response _________________________
    ig = Instagram("sessionid=x", rate_limiter=RateLimiter(0), budget=RequestBudget())
E   TypeError: Instagram.__init__() got an unexpected keyword argument 'rate_limiter'

========================== 2 failed in 0.79s ===========================
```

Matches the brief's expected failure exactly.

### GREEN (Step 8)

```
$ .venv/bin/pytest tests/test_instagram_softblock.py tests/test_ratelimit.py -v
```
```
collected 13 items

tests/test_instagram_softblock.py::test_goto_raises_on_login_redirect PASSED [  7%]
tests/test_instagram_softblock.py::test_goto_ok_returns_response PASSED     [ 15%]
tests/test_ratelimit.py::test_jittered_delay_within_bounds PASSED           [ 23%]
tests/test_ratelimit.py::test_jittered_delay_zero_range PASSED              [ 30%]
tests/test_ratelimit.py::test_backoff_delay_grows_and_caps PASSED           [ 38%]
tests/test_ratelimit.py::test_rate_limiter_spaces_calls PASSED              [ 46%]
tests/test_ratelimit.py::test_rate_limiter_disabled PASSED                  [ 53%]
tests/test_ratelimit.py::test_budget_counts_and_raises PASSED               [ 61%]
tests/test_ratelimit.py::test_budget_unlimited_when_none PASSED             [ 69%]
tests/test_ratelimit.py::test_detect_login_redirect PASSED                  [ 76%]
tests/test_ratelimit.py::test_detect_body_markers PASSED                    [ 84%]
tests/test_ratelimit.py::test_429_is_not_soft_block PASSED                  [ 92%]
tests/test_ratelimit.py::test_clean_response_is_none PASSED                 [100%]

============================== 13 passed in 0.05s ==============================
```

Also ran the full suite for a regression check:

```
$ .venv/bin/pytest tests/ -v
```
```
14 passed in 0.04s
```//
(the 14th is `tests/test_config.py::test_hardening_defaults_exist`, unaffected by this task)

## Files changed

- `modules/instagram.py` (28 insertions, 6 deletions) — imports, constructor,
  `_backoff_wait`, `_goto_with_retry`, three jittered sleeps, `get_profile_pic`.
- `tests/test_instagram_softblock.py` (new, 33 lines) — exact content from the brief.

Commit: `bac9dc0fcb985f547446aede1a57aa10bc47333f` —
"feat(instagram): pace requests, jitter delays, detect soft-blocks (Playwright)"

## Self-review

- Constructor defaults (`RateLimiter(0)`, `RequestBudget(None)`) preserve backward
  compatibility: every existing call site of `Instagram(...)` (in `search.py`, and
  the `face-osint` CLI, per CLAUDE.md architecture notes) continues to work
  unmodified with no-op pacing/unlimited budget, matching the brief's produced
  interface `Instagram(cookie_string, timeout=15000, skip_home=False,
  rate_limiter=None, budget=None)`.
- `_goto_with_retry`: budget is spent once per loop iteration (i.e., once per
  attempt including retries), which matches the brief's literal code — a
  429/exception retry consumes another unit of budget, which is intentional
  (each retry is a real HTTP request against Instagram).
- `SoftBlockError` is deliberately re-raised through its own `except SoftBlockError:
  raise` clause placed before the generic `except Exception:` — otherwise the
  generic handler would swallow it and retry, defeating the purpose of
  fail-fast soft-block detection.
- Verified the three jittered-sleep edits target exactly the call sites the brief
  describes (API followers pagination end, API following pagination end, modal
  scroll loop) by reading surrounding context before editing — did **not** touch
  the three `asyncio.sleep(0.5)` calls inside `_click_text` since the brief's
  line references (`:234,:302,:356` against the pre-Task-6 file) point only at
  the API-pagination and modal-scroll sleeps, not the click-text ones.
- Confirmed `modules/config.py` already has `BACKOFF_CAP = 300` and
  `DELAY_RANGE = (1.0, 3.0)` from earlier tasks — no config changes needed here.
  (Note: `DELAY_RANGE` itself isn't directly referenced in `instagram.py` per the
  brief; the jitter bounds used are the literal `(0.5,1.5)` / `(0.7,1.8)` pairs
  the brief specifies, not `config.DELAY_RANGE`. This matches the brief exactly
  as written.)
- Syntax-checked the modified file with `ast.parse` and ran the full test suite
  (14 tests) — all green, no regressions.

## Concerns

- `random` import in `modules/instagram.py` is now unused directly in that file
  (it's still used transitively via `modules.ratelimit`). The brief didn't ask to
  remove it, so it was left in place to stay strictly within scope — flagging in
  case a lint pass later wants it cleaned up.
- Per brief, `get_profile_pic`'s pre-existing "navigate home if not on
  instagram.com" block (`self.page.goto(...)` directly, not via
  `_goto_with_retry`) was **not** wrapped with pacing/budget/soft-block checks —
  the brief only specified adding those around the in-page `fetch` and the
  `page.request.get(url_data)` response check, so that raw `page.goto` call
  remains outside rate-limiter/budget/soft-block coverage. Flagging for
  awareness; not fixed since it's out of the brief's literal scope.
- This task only wires the primitives into `instagram.py`; it does not yet wire
  `rate_limiter`/`budget` instances through from `search.py`/CLI construction
  sites (i.e., callers still get the default no-op `RateLimiter(0)` /
  unlimited `RequestBudget(None)` unless a later task passes real instances in).
  That wiring appears to be a separate task per the plan's structure.
