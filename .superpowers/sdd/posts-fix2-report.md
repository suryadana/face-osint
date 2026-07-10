# posts-fix2 report

## Status
DONE.

## Commit
78b4701 — fix(posts): document consensus auto-stop + soft-block-check web_profile_info + Posts banner

## Verify
- `.venv/bin/pytest tests/ -v` → 27 passed (26 pre-existing + 1 new: `test_get_profile_media_raises_on_login_redirect`).
- `.venv/bin/python3.11 face-osint search` (no args) → usage prints correctly, includes `--posts N` row.

## Fixes applied
- FIX #1: `docs/penggunaan.md` already had an "Agregasi profil + post" section covering consensus/auto-stop; added an explicit callout paragraph matching the required wording (lone strong profile-pic hit ranks #1 but doesn't auto-stop; `--posts 0` = old behavior). Added a matching one-line note to `docs/keamanan-dan-rate-limit.md`'s volume section (optional, done — fits naturally next to the per-account request-volume discussion).
- FIX #2: `modules/instagram.py` `get_profile_media` — in-page fetch now returns `{__nonok, __status, __url, __body}` on non-ok instead of swallowing to `null`; Python side calls `detect_soft_block` on that and raises `SoftBlockError(kind, "profile_media")` for real soft-blocks, returns empty media dict for genuine non-2xx (e.g. 404) and for 429 (untouched, confirmed `detect_soft_block` returns None for both). `SoftBlockError`/`detect_soft_block` were already imported. `_check_one`'s `(SoftBlockError, BudgetExceeded)` handler untouched — propagation confirmed by new test. Added `test_get_profile_media_raises_on_login_redirect` to `tests/test_instagram_softblock.py` using the existing `_FakePage` style (extended with `evaluate_return`).
- FIX #4: added `print(f"  Posts:     {post_n}")` to `cmd_search` banner in `face-osint`, alongside Reference/Threshold/Workers/Depth.

## Deferred (explicitly out of scope, not done)
- Username escaping in JS (get_profile_media/get_profile_pic string interpolation).
- Strong-single-hit override to consensus rule.
- Zero-norm guard in face similarity.
- `--depth 0` honoring `--posts`.
