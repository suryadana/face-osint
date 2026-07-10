# Task 2-5 Report: Rate-Limit Hardening (RateLimiter, RequestBudget, soft-block detection, config knobs)

Branch: `feat/rate-limit-hardening`
Working directory: `/Users/suryadana/Learn/face-osint`

## Environment note (non-blocking, but worth recording)

The repo's `.venv` is a mixed/inconsistent virtualenv: `.venv/bin/python` symlinks to a bare
pyenv 3.9.19 interpreter with no packages installed (not even pip), while the actual installed
dependencies (pytest 9.1.1, pytest-asyncio 1.4.0, playwright, insightface, etc.) live under
`.venv/lib/python3.11/site-packages`, reachable via `.venv/bin/python3.11`. Additionally, this
machine has a global Claude Code hook (`rtk hook claude`, from `~/.claude/settings.json`) that
transparently rewrites Bash commands including `pytest`, and its pytest integration produced
stale/incorrect output in this session (a cached "No tests collected" result that did not
refresh across edits, and `rtk proxy pytest` resolving to an unrelated system Python 3.10.17
with pytest 7.1.3 and no pytest-asyncio, which silently *skipped* all async tests instead of
running them).

To get trustworthy TDD evidence I bypassed both issues and invoked the interpreter directly:

```
/Users/suryadana/Learn/face-osint/.venv/bin/python3.11 -m pytest ...
```

This resolves Python 3.11.15 / pytest 9.1.1 / pytest-asyncio 1.4.0 (`asyncio_mode = auto` from
`pytest.ini`), matching the environment the Task 1 baseline tests were already passing under.
All commands/output below are from this direct invocation. No source or test code was written to
work around the tooling — only the invocation path changed.

---

## Task 2: `RateLimiter` (global async pacer)

**Implemented:** Appended `RateLimiter` class to `modules/ratelimit.py` verbatim per brief —
constructor takes `rate_per_min`, `jitter_range=(0.0, 0.0)`, `time_fn=None`, `sleep_fn=None`;
computes `min_interval = 60/rate_per_min` (0.0 disables pacing); `async def acquire()` serializes
under an `asyncio.Lock`, waits until `_next_allowed`, then schedules the next slot using
`jittered_delay` for extra spacing.

**Files changed:** `modules/ratelimit.py`, `tests/test_ratelimit.py`

**RED:**
```
$ /Users/suryadana/Learn/face-osint/.venv/bin/python3.11 -m pytest tests/test_ratelimit.py -k rate_limiter -v
```
```
ERROR collecting tests/test_ratelimit.py
ImportError while importing test module '.../tests/test_ratelimit.py'.
tests/test_ratelimit.py:24: in <module>
    from modules.ratelimit import RateLimiter
E   ImportError: cannot import name 'RateLimiter' from 'modules.ratelimit' (.../modules/ratelimit.py)
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
```

**GREEN:**
```
$ /Users/suryadana/Learn/face-osint/.venv/bin/python3.11 -m pytest tests/test_ratelimit.py -k rate_limiter -v
```
```
tests/test_ratelimit.py::test_rate_limiter_spaces_calls PASSED  [ 50%]
tests/test_ratelimit.py::test_rate_limiter_disabled PASSED      [100%]
======================= 2 passed, 3 deselected ========================
```

**Commit:** `f5118ac` — `feat(ratelimit): add global RateLimiter with injectable clock`

**Deviation:** None. Code and tests transcribed exactly as specified in the brief.

---

## Task 3: `RequestBudget` + `BudgetExceeded`

**Implemented:** Appended `BudgetExceeded(Exception)` (attrs `.spent`, `.limit`) and
`RequestBudget` (constructor `max_requests=None`; `async def spend(self, n=1)` incrementing
`.spent` under an `asyncio.Lock`, raising `BudgetExceeded` once `spent > max_requests`; `None`
limit means unlimited) to `modules/ratelimit.py` verbatim per brief.

**Files changed:** `modules/ratelimit.py`, `tests/test_ratelimit.py`

**RED:**
```
$ /Users/suryadana/Learn/face-osint/.venv/bin/python3.11 -m pytest tests/test_ratelimit.py -k budget -v
```
```
ERROR collecting tests/test_ratelimit.py
ImportError while importing test module '.../tests/test_ratelimit.py'.
tests/test_ratelimit.py:56: in <module>
    from modules.ratelimit import RequestBudget, BudgetExceeded
E   ImportError: cannot import name 'RequestBudget' from 'modules.ratelimit' (.../modules/ratelimit.py)
```

**GREEN:**
```
$ /Users/suryadana/Learn/face-osint/.venv/bin/python3.11 -m pytest tests/test_ratelimit.py -k budget -v
```
```
tests/test_ratelimit.py::test_budget_counts_and_raises PASSED    [ 50%]
tests/test_ratelimit.py::test_budget_unlimited_when_none PASSED  [100%]
======================= 2 passed, 5 deselected ========================
```

**Commit:** `142cc4b` — `feat(ratelimit): add RequestBudget with hard cap`

**Deviation:** None.

---

## Task 4: `detect_soft_block` + `SoftBlockError`

**Implemented:** Appended `SoftBlockError(Exception)` (attr `.kind`) and `detect_soft_block(status,
url, body_text)` to `modules/ratelimit.py` verbatim per brief: returns `None` immediately for
HTTP 429 (throttle, handled by backoff elsewhere — not a soft block), `'login_redirect'` if the
URL contains `/accounts/login`, otherwise scans the lowercased body for
`checkpoint_required` / `challenge_required` / `feedback_required` markers and returns the
corresponding kind (`'checkpoint'`, `'challenge'`, `'feedback_required'`), else `None`.

**Files changed:** `modules/ratelimit.py`, `tests/test_ratelimit.py`

**RED:**
```
$ /Users/suryadana/Learn/face-osint/.venv/bin/python3.11 -m pytest tests/test_ratelimit.py -k "soft or detect or 429 or clean" -v
```
```
ERROR collecting tests/test_ratelimit.py
ImportError while importing test module '.../tests/test_ratelimit.py'.
tests/test_ratelimit.py:77: in <module>
    from modules.ratelimit import detect_soft_block, SoftBlockError
E   ImportError: cannot import name 'detect_soft_block' from 'modules.ratelimit' (.../modules/ratelimit.py)
```

**GREEN:**
```
$ /Users/suryadana/Learn/face-osint/.venv/bin/python3.11 -m pytest tests/test_ratelimit.py -k "soft or detect or 429 or clean" -v
```
```
tests/test_ratelimit.py::test_detect_login_redirect PASSED   [ 25%]
tests/test_ratelimit.py::test_detect_body_markers PASSED     [ 50%]
tests/test_ratelimit.py::test_429_is_not_soft_block PASSED   [ 75%]
tests/test_ratelimit.py::test_clean_response_is_none PASSED  [100%]
======================= 4 passed, 7 deselected ========================
```

**Commit:** `b052591` — `feat(ratelimit): add soft-block detection + SoftBlockError`

**Deviation:** The brief's Step 4 says "Expected: PASS (5 passed)" but the filter
`-k "soft or detect or 429 or clean"` selects exactly 4 test *functions* (one of which,
`test_detect_body_markers`, contains 3 assertions for the 3 body markers — brief likely miscounted
assertions as tests). All 4 collected tests pass; no functional gap. Not a code deviation, purely
a discrepancy in the brief's expected-count comment.

---

## Task 5: Config knobs

**Implemented:** Created `tests/test_config.py` per brief, then added to `modules/config.py`
(after `MAX_DEPTH = 3`) the constants exactly as specified: `RATE_PER_MIN = 20`,
`DELAY_RANGE = (1.0, 3.0)`, `MAX_REQUESTS = 800`, `MAX_EXPANSIONS_PER_LAYER = 15`,
`BACKOFF_CAP = 300`.

**Files changed:** `modules/config.py`, `tests/test_config.py` (new)

**RED:**
```
$ /Users/suryadana/Learn/face-osint/.venv/bin/python3.11 -m pytest tests/test_config.py -v
```
```
tests/test_config.py::test_hardening_defaults_exist FAILED [100%]
    assert config.RATE_PER_MIN == 20
E   AttributeError: module 'modules.config' has no attribute 'RATE_PER_MIN'
============================== 1 failed in 0.03s ===============================
```

**GREEN:**
```
$ /Users/suryadana/Learn/face-osint/.venv/bin/python3.11 -m pytest tests/test_config.py -v
```
```
tests/test_config.py::test_hardening_defaults_exist PASSED [100%]
============================== 1 passed in 0.00s ===============================
```

**Commit:** `774e416` — `feat(config): add rate-limit hardening knobs`

**Deviation:** None.

---

## Final full-suite run (after all 4 commits)

```
$ /Users/suryadana/Learn/face-osint/.venv/bin/python3.11 -m pytest
```
```
collected 12 items
tests/test_config.py .                                                   [  8%]
tests/test_ratelimit.py ...........                                      [100%]
============================== 12 passed in 0.01s ==============================
```

## Commit summary

| Task | SHA       | Subject |
|------|-----------|---------|
| 2    | `f5118ac` | feat(ratelimit): add global RateLimiter with injectable clock |
| 3    | `142cc4b` | feat(ratelimit): add RequestBudget with hard cap |
| 4    | `b052591` | feat(ratelimit): add soft-block detection + SoftBlockError |
| 5    | `774e416` | feat(config): add rate-limit hardening knobs |

No global constraints were violated: no raw HTTP clients added, no Python 3.10+ syntax used
(no `match`, no `X | Y` unions), all time/random logic in new code accepts injectable
`time_fn`/`sleep_fn`/`rng`, `import asyncio` was reused from Task 1 (no duplicate import added).
