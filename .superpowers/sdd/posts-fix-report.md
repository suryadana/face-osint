# Review fixes — face-compare-posts (2026-07-10)

Branch: `feat/face-compare-posts`

## FIX #1 — `--posts 0` backward-compat regression

**Problem**: `_check_one` computed `decide_account(scores, ..., config.CONSENSUS_MIN)` unconditionally
(`CONSENSUS_MIN=2`). With `post_n=0` only 1 image (profile pic) is ever scored, so `matched` could
never reach 2 → `is_match` always `False` → old single-image `sim>=threshold` behavior was broken.

**Fix**: `modules/search.py`
- `modules/search.py:74` — added `effective_consensus = min(config.CONSENSUS_MIN, 1 + self.post_n)`
  computed once per `_check_one` call, right before the profile-pic download.
- `modules/search.py:80` — early-stop check inside the post loop now uses `effective_consensus`
  instead of `config.CONSENSUS_MIN`.
- `modules/search.py:87` — final decision call now uses `effective_consensus` instead of
  `config.CONSENSUS_MIN`.
- `config.CONSENSUS_MIN` itself left unchanged (still 2).

Net effect: `post_n=0` → `effective_consensus=1` (old single-hit match restored);
`post_n>=1` → `effective_consensus=2` (unchanged, since `1+post_n >= 2`).

**Test added**: `tests/test_decide_account.py:28` — `test_single_image_matches_when_consensus_one`
proves `decide_account([0.50], threshold=0.35, consensus_min=1)["is_match"] is True`, i.e. the
consensus=1 semantics the `post_n=0` path now relies on.

## FIX #2 — `get_profile_media` / `download_image` bypass pacing/budget/soft-block

**Problem**: Unlike `get_profile_pic` (which does `acquire()`+`spend()` before its fetch and checks
`detect_soft_block(...)` after `page.request.get`), `get_profile_media` and `download_image` ran
ungoverned — defeating the rate-limit hardening (no pacing, no budget accounting, no soft-block
detection) for the new per-account media/post-image fetch path.

**Fix**: `modules/instagram.py`

- `get_profile_media` (`modules/instagram.py:460`):
  - (a) Replaced the bare `try: await self.page.goto("https://www.instagram.com/", ...) except
    Exception: pass` home-navigation with `await self._goto_with_retry("https://www.instagram.com/")`
    — now paced, budgeted, and soft-block-checked (via `_goto_with_retry`'s internal
    `acquire()`/`spend()`/`detect_soft_block` and `SoftBlockError` propagation). No longer swallows
    errors silently.
  - (b) Added `await self.rate_limiter.acquire()` and `await self.budget.spend()` immediately
    before the in-page `web_profile_info` `fetch()` evaluate call (`modules/instagram.py:465-466`).

- `download_image` (`modules/instagram.py:482`):
  - After `resp = await self.page.request.get(url)`, added
    `kind = detect_soft_block(resp.status, url, ""); if kind: raise SoftBlockError(kind,
    "post_image")` before the `resp.ok` body return — mirrors `get_profile_pic`'s existing check.

`detect_soft_block` and `SoftBlockError` were already imported in `modules/instagram.py` (from
`modules.ratelimit`, line 8-11) from the prior rate-limit-hardening work — no new imports needed.

`_check_one`'s existing `except (SoftBlockError, BudgetExceeded)` handler
(`modules/search.py:96-100`) was **not** modified; it already catches and gracefully stops on these
newly-propagated exceptions from both functions.

## Verification

### 1. `.venv/bin/pytest tests/ -v`

Before fix (baseline): 25 passed.
After fix: **26 passed** (25 + 1 new `test_single_image_matches_when_consensus_one`).

```
collected 26 items

tests/test_config.py::test_hardening_defaults_exist PASSED             [  3%]
tests/test_decide_account.py::test_ranking_max_and_consensus_match PASSED [  7%]
tests/test_decide_account.py::test_single_hit_is_not_match_under_consensus PASSED [ 11%]
tests/test_decide_account.py::test_all_none_gives_none_score PASSED    [ 15%]
tests/test_decide_account.py::test_boundary_score_equals_threshold_is_match PASSED [ 19%]
tests/test_decide_account.py::test_single_image_matches_when_consensus_one PASSED [ 23%]
tests/test_face_agg.py::test_max_similarity_picks_best PASSED          [ 26%]
tests/test_face_agg.py::test_max_similarity_empty_is_none PASSED       [ 30%]
tests/test_instagram_softblock.py::test_goto_raises_on_login_redirect PASSED [ 34%]
tests/test_instagram_softblock.py::test_goto_ok_returns_response PASSED [ 38%]
tests/test_profile_media.py::test_parse_extracts_pic_and_posts PASSED  [ 42%]
tests/test_profile_media.py::test_parse_falls_back_to_lo_pic_and_empty_posts PASSED [ 46%]
tests/test_profile_media.py::test_parse_handles_missing_user PASSED    [ 50%]
tests/test_ratelimit.py::test_jittered_delay_within_bounds PASSED      [ 53%]
tests/test_ratelimit.py::test_jittered_delay_zero_range PASSED         [ 57%]
tests/test_ratelimit.py::test_backoff_delay_grows_and_caps PASSED      [ 61%]
tests/test_ratelimit.py::test_rate_limiter_spaces_calls PASSED         [ 65%]
tests/test_ratelimit.py::test_rate_limiter_disabled PASSED             [ 69%]
tests/test_ratelimit.py::test_budget_counts_and_raises PASSED          [ 73%]
tests/test_ratelimit.py::test_budget_unlimited_when_none PASSED        [ 76%]
tests/test_ratelimit.py::test_detect_login_redirect PASSED             [ 80%]
tests/test_ratelimit.py::test_detect_body_markers PASSED               [ 84%]
tests/test_ratelimit.py::test_429_is_not_soft_block PASSED             [ 88%]
tests/test_ratelimit.py::test_clean_response_is_none PASSED            [ 92%]
tests/test_search_limits.py::test_cap_expansions_limits_count PASSED   [ 96%]
tests/test_search_limits.py::test_cap_expansions_none_disables PASSED  [100%]

============================== 26 passed in 0.20s ==============================
```

### 2. `.venv/bin/python3.11 face-osint search` (no args)

Usage still prints (exit code 1), includes `--posts`:

```
Usage: face-osint search <ref_image> <instagram_username> [options]
Options:
  --depth N     Graph depth (0=user only, 1=followers/following, 2=their friends, ...)
  --workers N   Parallel workers (default 3)
  --threshold X Match threshold 0-1 (default 0.35)
  --no-cache    Re-scrape followers/following, ignore saved cache
  --posts N     Recent posts sampled per account (default 3; 0=profile pic only)
  --rate N        Global read pace, requests/min (default 20; 0=off)
  --max-requests N  Per-run request budget (default 800)
  --max-expand N  Max accounts expanded per layer (default 15)
  --delay-min X / --delay-max X  Jittered inter-action delay seconds

Examples:
  face-osint search ref.jpg target_user --depth 1
  face-osint search ref.jpg target_user --depth 3 --workers 5
```

## Commit

`fix(posts): --posts 0 single-hit match + govern get_profile_media/download_image (pace+budget+soft-block)`
