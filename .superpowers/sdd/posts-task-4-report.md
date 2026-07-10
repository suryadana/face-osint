# Task 4 Report: Wire post-aggregation into BFS search + config + CLI + docs

Branch: `feat/face-compare-posts`

## What changed (file:line)

### `modules/config.py` (+4, after existing constants, ~line 27-30)
Added:
```python
# --- Post-image aggregation ---
POST_SAMPLE_N = 3      # recent posts sampled per checked account (0 = profile pic only)
CONSENSUS_MIN = 2      # distinct images >= SIM_THRESHOLD required to auto-stop (FOUND)
```

### `modules/search.py`
- `BFSSearch.__init__` (line 29-34): added `post_n=None` param; `self.post_n = config.POST_SAMPLE_N if post_n is None else post_n`.
- `_check_one` (line 62-91): replaced the old `get_profile_pic` + `compare_to_ref` single-image check with media aggregation exactly per brief:
  - `ig.get_profile_media(username)` → `pic_url`, dedup via `checked_urls` lock as before.
  - `scores = []`; download+score profile pic via `max_similarity_to_ref`.
  - Loop over `media["post_urls"][:self.post_n]`: before each download, call `decide_account(scores, ...)`; break early if `is_match` (consensus already reached) — this is the early-stop that avoids downloading all N posts once consensus is hit.
  - Final `decision = decide_account(scores, config.SIM_THRESHOLD, config.CONSENSUS_MIN)`; append `decision["score"]` to `self.results` if not None; set `self.found`/`self.found_data` on `decision["is_match"]`.
  - `decide_account` needed no new import — it's already module-level in `modules/search.py` (Task 3, committed as `3dc3701`).

### `face-osint`
- Top docstring (~line 8-9): added `--posts N` line to the `search` options list.
- `cmd_search` usage block (~line 159-160): added `--posts N` help line.
- `cmd_search` defaults (~line 176-177): added `post_n = config.POST_SAMPLE_N`.
- `cmd_search` arg-parse loop (~line 192-193): added `--posts` flag handling (`int(args[i+1])`).
- `BFSSearch(...)` construction (~line 253): added `post_n=post_n`.

### `tests/test_decide_account.py` (+5, appended)
Added the requested boundary test:
```python
def test_boundary_score_equals_threshold_is_match():
    r = decide_account([0.35], threshold=0.35, consensus_min=1)
    assert r["is_match"] is True
```
(Score == threshold uses `>=` in `decide_account`, so this is `True` — matches existing implementation, no code change needed there.)

### `docs/penggunaan.md`
- Added `--posts N` row to the `search` options table (default `3`, note `0` = profile pic only).
- Added new subsection "Agregasi profil + post (`--posts`)" explaining: per-image scoring via `max_similarity_to_ref`, ranking by max score across all checked images, auto-stop via consensus (`config.CONSENSUS_MIN`, default 2 images ≥ `SIM_THRESHOLD`), early-stop behavior, and `--posts 0` back-compat.

### `docs/keamanan-dan-rate-limit.md`
- Updated "Model volume request" paragraph: per-account cost for profile-pic-only is unchanged (~3 request/akun), but with `--posts N` aggregation it rises to **~3 + (1..N) request/akun**, bounded by how many posts are actually downloaded before consensus is reached or `post_urls` is exhausted. Noted that post-image downloads go through the same `download_image` → `rate_limiter`/`budget` path as other requests, so the extra volume is still governed by `--rate`/`--max-requests`, not unbounded. Left the depth 1/2/3 order-of-magnitude table (~10³/10⁵/10⁶–10⁷) unchanged since a small constant multiplier (1-3x) doesn't change the order of magnitude.

## Verification evidence

### 1. `.venv/bin/pytest tests/ -v`
```
collected 25 items

tests/test_config.py::test_hardening_defaults_exist PASSED             [  4%]
tests/test_decide_account.py::test_ranking_max_and_consensus_match PASSED [  8%]
tests/test_decide_account.py::test_single_hit_is_not_match_under_consensus PASSED [ 12%]
tests/test_decide_account.py::test_all_none_gives_none_score PASSED    [ 16%]
tests/test_decide_account.py::test_boundary_score_equals_threshold_is_match PASSED [ 20%]
tests/test_face_agg.py::test_max_similarity_picks_best PASSED          [ 24%]
tests/test_face_agg.py::test_max_similarity_empty_is_none PASSED       [ 28%]
tests/test_instagram_softblock.py::test_goto_raises_on_login_redirect PASSED [ 32%]
tests/test_instagram_softblock.py::test_goto_ok_returns_response PASSED [ 36%]
tests/test_profile_media.py::test_parse_extracts_pic_and_posts PASSED  [ 40%]
tests/test_profile_media.py::test_parse_falls_back_to_lo_pic_and_empty_posts PASSED [ 44%]
tests/test_profile_media.py::test_parse_handles_missing_user PASSED    [ 48%]
tests/test_ratelimit.py::test_jittered_delay_within_bounds PASSED      [ 52%]
tests/test_ratelimit.py::test_jittered_delay_zero_range PASSED         [ 56%]
tests/test_ratelimit.py::test_backoff_delay_grows_and_caps PASSED      [ 60%]
tests/test_ratelimit.py::test_rate_limiter_spaces_calls PASSED         [ 64%]
tests/test_ratelimit.py::test_rate_limiter_disabled PASSED             [ 68%]
tests/test_ratelimit.py::test_budget_counts_and_raises PASSED          [ 72%]
tests/test_ratelimit.py::test_budget_unlimited_when_none PASSED        [ 76%]
tests/test_ratelimit.py::test_detect_login_redirect PASSED             [ 80%]
tests/test_ratelimit.py::test_detect_body_markers PASSED               [ 84%]
tests/test_ratelimit.py::test_429_is_not_soft_block PASSED             [ 88%]
tests/test_ratelimit.py::test_clean_response_is_none PASSED            [ 92%]
tests/test_search_limits.py::test_cap_expansions_limits_count PASSED   [ 96%]
tests/test_search_limits.py::test_cap_expansions_none_disables PASSED  [100%]

============================== 25 passed in 0.20s ==============================
```
25 passing (24 pre-existing + 1 new boundary test), matches expectation exactly.

### 2. `.venv/bin/python3.11 face-osint search` (no args, exit code 1)
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
`--posts N` line present, as required.

### Step 4 (manual real-run verification) — NOT PERFORMED
No Instagram cookie/network available in this environment per task instructions ("do NOT attempt a real search"). Skipped per explicit instruction in the task brief/prompt. This is a known gap versus the brief's Step 4 (real-run smoke with `--cookie` against a live account) — purely offline verification (pytest + CLI usage) was performed instead, as directed.

## Files changed
- `modules/config.py`
- `modules/search.py`
- `face-osint`
- `tests/test_decide_account.py`
- `docs/penggunaan.md`
- `docs/keamanan-dan-rate-limit.md`

(Note: `.superpowers/sdd/task-1-brief.md` through `task-4-brief.md` and `.superpowers/sdd/progress.md` showed as modified in `git status` at session start — these were already dirty before this task began and were NOT touched by this task's work. They are left untouched/uncommitted by this task's commit, which only stages the 6 files above.)

## Self-review

- Code in `modules/search.py` `_check_one` matches the brief's snippet verbatim (variable names, control flow, break condition, lock scoping identical).
- `config.py` additions match verbatim (comment text, values).
- CLI additions (`--posts` parsing, help lines, `post_n=` passthrough) match brief verbatim.
- Backward compat: `--posts 0` / `POST_SAMPLE_N=0` → `media["post_urls"][:0]` is `[]`, loop body never runs, `scores` only ever has the profile-pic score → identical to old profile-pic-only behavior (modulo `compare_to_ref` vs `max_similarity_to_ref`, which was already changed in Task 1 to be multi-face-aware but functionally equivalent for a single-face image).
- Python 3.9 compatibility: no `match` statement, no `X | Y` type unions introduced.
- Scraping-related work still only uses `Instagram.get_profile_media`/`download_image`, both Playwright-backed (verified in `modules/instagram.py` — `download_image` uses `self.page.request.get`, `get_profile_media` uses in-page `fetch()` via `page.evaluate`). No raw-HTTP client added.
- Test added exactly as specified: `decide_account([0.35], threshold=0.35, consensus_min=1)["is_match"] is True` — passes because `decide_account` uses `s >= threshold` (line 24 of `modules/search.py`), so `0.35 >= 0.35` counts as 1 match, `1 >= consensus_min(1)` → True. No implementation change needed for this to hold; it was already correct.
- Commit co-author trailer set per instructions.

## Concerns

1. **Real-run manual verification (brief Step 4) was not performed** — no cookie/network in this environment, and the task instructions explicitly said not to attempt a real search. This means the actual behavioral claim in the brief ("post version should surface a score where profile-pic-only detected no face") is unverified end-to-end in this session. Recommend a follow-up manual smoke test with a real cookie before merging to `dev`/`main`, per the brief's own Step 4.
2. Did not add a `Posts:` line to the `cmd_search` startup print block (which prints `Reference:`, `Threshold:`, `Workers:`, `Depth:`) — this is a minor UX nicety not required by the brief, omitted to avoid scope creep beyond the exact spec.
3. The volume-model doc update is qualitative/order-of-magnitude (kept the existing ~10³/10⁵/10⁶–10⁷ table as-is since a 1-4x per-account multiplier doesn't change order of magnitude) rather than recomputing exact numbers — this matches the brief's instruction ("per-account cost rises to ~3 + (1..N)... bounded by limiter/budget + consensus early-stop") which asked for the narrative update, not a new table.
