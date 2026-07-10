# Task 8 Report: CLI flags + docs (final task of rate-limit hardening)

## Status: DONE

Branch: `feat/rate-limit-hardening`
Commit: `517dc99` — "feat(cli): expose rate/budget/expand/delay flags + document"

## Implemented (per brief, verbatim)

### `face-osint`
1. Added `from modules.ratelimit import RateLimiter, RequestBudget` import.
2. `cmd_search` usage block (Step 3): added 4 new help lines for `--rate`,
   `--max-requests`, `--max-expand`, `--delay-min`/`--delay-max`.
3. `cmd_search` defaults block: `rate = config.RATE_PER_MIN`,
   `max_requests = config.MAX_REQUESTS`, `max_expand = config.MAX_EXPANSIONS_PER_LAYER`,
   `delay_min, delay_max = config.DELAY_RANGE`.
4. `cmd_search` arg-parse loop: added `elif` branches for `--rate` (int),
   `--max-requests` (int), `--max-expand` (int), `--delay-min` (float),
   `--delay-max` (float) — inserted before the existing `else: i += 1`.
5. Before constructing `BFSSearch`: build
   `limiter = RateLimiter(rate, jitter_range=(delay_min, delay_max))`,
   `budget = RequestBudget(max_requests)`, and
   `config.MAX_EXPANSIONS_PER_LAYER = max_expand` (CLI override).
6. `BFSSearch(...)` constructor call now passes `rate_limiter=limiter, budget=budget`
   in addition to the existing `ref_path, cookie_string, workers, face_engine, ref_emb`.
7. After `search(...)` returns (right after computing `elapsed`), added:
   `if searcher.stop_reason: print(f"\n  STOPPED early (safety): {searcher.stop_reason}")`.

Diff is exactly 29 insertions / 1 deletion in `face-osint`, matching the brief's
code blocks verbatim (variable names, flag names, print strings all match).

### Docs
- `docs/penggunaan.md`: added 4 new rows to the `search` options table
  (`--rate` 20, `--max-requests` 800, `--max-expand` 15, `--delay-min`/`--delay-max`
  1.0/3.0), a new example invocation using the flags, a new explanatory block about
  the `STOPPED early (safety): ...` output, and a note in the existing depth-2+
  warning that the new flags reduce but don't eliminate risk.
- `docs/keamanan-dan-rate-limit.md`: rewrote "Mitigasi yang sudah ada" section —
  removed the old "hanya menurunkan volume, lemah di rate" framing (no longer
  true) and listed the 6 concrete implemented mitigations (global rate limiter,
  jitter delay, soft-block hard-stop, request budget, expansion cap, backoff cap
  300s) with their CLI flags/defaults. Updated "Faktor risiko" to strike through
  the 3 items now fixed (unbounded expansion, fixed delay, 429-only detection)
  and kept the still-open risks (single session/no proxy, non-cross-worker
  backoff) explicitly marked as unmitigated/deferred. Updated the 7-item
  "Playbook" list to mark items 3, 5, 6 as "✅ Sudah default" (now built-in via
  flags) while keeping 1, 2, 4, 7 as manual/operator responsibility.

## Verification evidence

### 1. Unit suite — `.venv/bin/pytest tests/ -v`

```
collected 16 items

tests/test_config.py::test_hardening_defaults_exist PASSED             [  6%]
tests/test_instagram_softblock.py::test_goto_raises_on_login_redirect PASSED [ 12%]
tests/test_instagram_softblock.py::test_goto_ok_returns_response PASSED [ 18%]
tests/test_ratelimit.py::test_jittered_delay_within_bounds PASSED      [ 25%]
tests/test_ratelimit.py::test_jittered_delay_zero_range PASSED         [ 31%]
tests/test_ratelimit.py::test_backoff_delay_grows_and_caps PASSED      [ 37%]
tests/test_ratelimit.py::test_rate_limiter_spaces_calls PASSED         [ 43%]
tests/test_ratelimit.py::test_rate_limiter_disabled PASSED             [ 50%]
tests/test_ratelimit.py::test_budget_counts_and_raises PASSED          [ 56%]
tests/test_ratelimit.py::test_budget_unlimited_when_none PASSED        [ 62%]
tests/test_ratelimit.py::test_detect_login_redirect PASSED             [ 68%]
tests/test_ratelimit.py::test_detect_body_markers PASSED               [ 75%]
tests/test_ratelimit.py::test_429_is_not_soft_block PASSED             [ 81%]
tests/test_ratelimit.py::test_clean_response_is_none PASSED            [ 87%]
tests/test_search_limits.py::test_cap_expansions_limits_count PASSED   [ 93%]
tests/test_search_limits.py::test_cap_expansions_none_disables PASSED  [100%]

============================== 16 passed in 0.40s ==============================
```

Stayed green, no regressions (16 passing, same count as before this task).

### 2. CLI help smoke test — `.venv/bin/python3.11 face-osint search`

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
EXIT_CODE=1
```

Confirms: all 4 new flag help lines present, no cookie/network needed, exit
code 1 (non-zero) as expected for the "too few args" usage path. Also
confirmed `ast.parse` succeeds on `face-osint` (valid syntax) before running.

No real network search was attempted (no IG cookie available), per instructions.

## Files changed

- `/Users/suryadana/Learn/face-osint/face-osint` (modified)
- `/Users/suryadana/Learn/face-osint/docs/penggunaan.md` (newly tracked — see note below)
- `/Users/suryadana/Learn/face-osint/docs/keamanan-dan-rate-limit.md` (newly tracked — see note below)

**Note on docs tracking state:** the entire `docs/` directory was untracked in
git before this task (not gitignored, just never `git add`ed in any prior
commit on this branch or `main`). This task's commit is the first to add
`docs/penggunaan.md` and `docs/keamanan-dan-rate-limit.md` to git (shown as
`create mode 100644` / `A` in the diff/status even though the files
pre-existed on disk with content). Other doc files (`docs/README.md`,
`docs/arsitektur.md`, `docs/instalasi.md`, `docs/troubleshooting.md`,
`docs/superpowers/`) remain untracked — out of scope for this task's brief,
left untouched.

## Self-review

- Every code change matches the brief's code blocks verbatim: flag names,
  variable names (`rate`, `max_requests`, `max_expand`, `delay_min`,
  `delay_max`, `limiter`, `budget`), the `config.MAX_EXPANSIONS_PER_LAYER =
  max_expand` CLI-override line, the exact `BFSSearch(...)` call signature,
  and the exact `STOPPED early (safety): ...` print.
- Confirmed interfaces before wiring: read `modules/ratelimit.py` (`RateLimiter(rate_per_min,
  jitter_range=(lo,hi))`, `RequestBudget(max_requests)`), `modules/search.py`
  (`BFSSearch.__init__` already accepts `rate_limiter=`/`budget=` from Task 7,
  exposes `self.stopped`/`self.stop_reason`), and `modules/config.py`
  (`RATE_PER_MIN=20`, `DELAY_RANGE=(1.0,3.0)`, `MAX_REQUESTS=800`,
  `MAX_EXPANSIONS_PER_LAYER=15` all present from Task 3). All match brief
  assumptions exactly — no interface drift to reconcile.
- Checked the brief's "Files" note about `_scrape_user`/`Instagram(...)`
  sites: `Instagram.__init__` (modules/instagram.py:57-58) already defaults
  `rate_limiter=None -> RateLimiter(0)` and `budget=None -> RequestBudget(None)`
  (both no-op/unlimited), so the 4 other `Instagram(cookie)` call sites
  (`_depth0_check`, `_scrape_user`, `cmd_scrape`, `cmd_pic`) safely no-op on
  rate-limiting without needing changes — consistent with the brief's actual
  Steps 1-3, which only touch `cmd_search`'s `BFSSearch` construction. Did not
  expand scope to wire the limiter into these other paths since the brief
  didn't ask for it and doing so wasn't part of the 6 listed steps.
- Placement of the `STOPPED early` print: put it immediately after `elapsed =
  time.time() - t0` (before the "Done in Xs" print), rather than at the very
  end of `cmd_search`, so it surfaces prominently right where the search
  result is first reported. This is a reasonable interpretation of "After
  search(...) returns" — brief didn't pin an exact line, and this placement
  keeps it grouped with elapsed/results reporting rather than buried after
  the top-20 dump.
- Docs: went slightly beyond a minimal table-row addition to also update the
  narrative/example sections and playbook status markers, since the brief
  said "replace the caveats that are now fixed" and "note ... as implemented
  mitigations" — a bare table row alone wouldn't have satisfied that framing
  requirement. Did not touch `docs/README.md`, `docs/arsitektur.md`,
  `docs/instalasi.md`, or `docs/troubleshooting.md` — out of scope per brief.
- Did not modify the top-level module docstring (`face-osint` lines 1-35,
  shown by `--help`/`-h`) — brief's Step 3 specifically named the `cmd_search`
  usage block (`:150-158` in the original numbering), not the top docstring.
  Left it alone to avoid unrequested scope creep.

## Concerns

- None blocking. One minor observation: `--max-requests`/`--rate` etc. have
  no input validation (e.g., negative or zero values aren't rejected beyond
  what `RateLimiter`/`RequestBudget` already handle internally — `rate<=0`
  disables pacing by design, `max_requests` however would need to be
  explicitly `None` to disable, and CLI can't currently pass `None` for
  `--max-requests` since `int(args[i+1])` errors on non-numeric input). This
  matches the brief's exact spec (no validation was requested) and mirrors
  the existing style of `--workers`/`--depth`/`--threshold` parsing elsewhere
  in the file, so not treated as a defect.
- Manual verification Step 4 (real network run with a cookie hitting the
  budget cap) was explicitly excluded per task instructions (no cookie
  available) — only the two no-network verification steps were run, as
  directed.
