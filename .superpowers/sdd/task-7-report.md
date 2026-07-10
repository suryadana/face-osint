# Task 7 Report: Enforce cap + graceful stop in `search.py`

## Status: DONE

## Summary

Wired `rate_limiter`/`budget` into `BFSSearch`, passed them through to every
`Instagram(...)` construction site, added an expansion cap per BFS layer via
a new `cap_expansions()` helper, and added graceful-stop handling for
`SoftBlockError`/`BudgetExceeded` in both the per-account face-check path and
the layer-expansion (followers/following fetch) path.

## TDD Evidence

### RED (Step 2)

Command:
```
.venv/bin/pytest tests/test_search_limits.py -v
```

Output (relevant excerpt):
```
ImportError while importing test module '/Users/suryadana/Learn/face-osint/tests/test_search_limits.py'.
tests/test_search_limits.py:2: in <module>
    from modules.search import cap_expansions
E   ImportError: cannot import name 'cap_expansions' from 'modules.search' (/Users/suryadana/Learn/face-osint/modules/search.py)
Interrupted: 1 error during collection
```

Matches the brief's expected failure exactly.

### GREEN (Step 5)

Command:
```
.venv/bin/pytest tests/test_search_limits.py -v
```

Output:
```
tests/test_search_limits.py::test_cap_expansions_limits_count PASSED   [ 50%]
tests/test_search_limits.py::test_cap_expansions_none_disables PASSED  [100%]

============================== 2 passed in 0.23s ===============================
```

### Full suite (regression check)

Command:
```
.venv/bin/pytest tests/ -v
```

Output: `16 passed in 0.24s` — all prior tests (`test_config.py`,
`test_instagram_softblock.py`, `test_ratelimit.py`) plus the 2 new ones pass.

### Python 3.9 syntax compatibility check

```
python3.9 -c "import ast; ast.parse(open('modules/search.py').read()); print('py3.9 syntax OK')"
```
Output: `py3.9 syntax OK` (no `match`, no `X | Y` unions used).

## Files changed

- `modules/search.py`:
  - Added `from modules.ratelimit import SoftBlockError, BudgetExceeded`.
  - Added module-level `cap_expansions(candidates, max_per_layer)` helper (verbatim from brief).
  - `BFSSearch.__init__` now accepts `rate_limiter=None, budget=None`, stores them, plus new `self.stopped = asyncio.Event()` and `self.stop_reason = None`.
  - `_check_one`: `Instagram(...)` call now passes `rate_limiter=self.rate_limiter, budget=self.budget`; added `except (SoftBlockError, BudgetExceeded) as e:` block that sets `self.stop_reason`, sets `self.stopped`, sets `self.found` (to unwind all concurrent phase-1 tasks via the existing short-circuit), and returns `None`.
  - `search()`: after computing `expand` (post dedup against `expanded_users`), inserted `expand = cap_expansions(expand, config.MAX_EXPANSIONS_PER_LAYER)` before the expansion loop.
  - Expansion loop's `Instagram(...)` call (previously `:119`) now also passes `rate_limiter=self.rate_limiter, budget=self.budget`, and gained an `except (SoftBlockError, BudgetExceeded)` clause identical in effect to the one in `_check_one` (sets `stop_reason`/`stopped`/`found`, then `break`s out of the expansion `for` loop instead of `continue`, since continuing to expand more accounts after a detected soft-block/budget-exceeded would defeat the point of stopping).
- `tests/test_search_limits.py` (new): the two tests exactly as specified in the brief.

## Self-review

- Brief only explicitly showed the exception-handling snippet being added to `_check_one`, but the task description says "(3) stop the whole search gracefully when `SoftBlockError` or `BudgetExceeded` is raised" — singular concern applying to the whole search, not just one call site. The expansion loop's `Instagram(...)` call (`:141` after edits) performs `get_followers`/`get_following`, which are equally capable of raising these errors (they go through the same rate-limited/budgeted Playwright network path in `instagram.py`). Leaving that site uncovered would mean a soft-block detected mid-expansion just gets swallowed by the generic `except Exception` handler, prints "Error fetching @user: soft-block: ..." and the loop keeps expanding into more accounts — the opposite of "graceful stop." I added the same catch there, using `break` (not `continue`) so the expansion loop itself halts immediately, then relies on `self.found.is_set()` checks already present in the recursive-call sites to unwind further. This is a deliberate interpretation beyond the brief's literal Step 3 snippet; flagging it explicitly in case reviewers want it scoped back to only `_check_one`.
- Did not modify `face-osint` (the CLI entry point) to actually construct/pass a `RateLimiter`/`RequestBudget` into `BFSSearch(...)` — that wiring is out of scope per the task description ("Task 7... wires limits into the BFS engine"), and the brief's file list only names `modules/search.py` and the test file. `BFSSearch(rate_limiter=None, budget=None)` remains fully backward-compatible (defaults preserve old behavior), so existing callers are unaffected. This is presumably a later task (CLI wiring) — flagging so it isn't assumed already done.
- Did not add a test asserting that `_check_one` or the expansion loop actually sets `self.stopped`/`self.stop_reason` on a raised `SoftBlockError`/`BudgetExceeded` (e.g., an async test with a stubbed `Instagram`) — the brief's Step 1 test list only covers `cap_expansions`. Given the "exact code/values verbatim" instruction and that the brief didn't specify such a test, I did not invent one, but this is a coverage gap worth knowing about: the stop-flag behavior is currently exercised only by manual code review, not by an automated test.
- Verified `config.MAX_EXPANSIONS_PER_LAYER` already exists (`= 15`) from a prior task — no config change needed here.
- Verified `Instagram.__init__` in `modules/instagram.py` already accepts `rate_limiter=None, budget=None` (from Tasks 1-6), confirming the interface assumption in the brief.

## Concerns

1. Expansion-loop exception handling was added beyond the brief's literal Step 3 diff (see self-review above) — a judgment call to satisfy the task's overall intent ("stop the whole search gracefully"). Worth a reviewer's explicit sign-off.
2. No automated test exercises the actual stop-on-exception behavior (only `cap_expansions` is unit-tested, per the brief). If a future task needs regression coverage for `self.stopped`/`self.stop_reason`, that test does not yet exist.
3. `face-osint` (CLI) still does not construct a `RateLimiter`/`RequestBudget` or read `self.stopped`/`self.stop_reason` after a search to report why a search halted — assumed to be a later task in the plan.
