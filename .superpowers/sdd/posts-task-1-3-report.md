# face-compare-posts: Tasks 1-3 Report

Branch: `feat/face-compare-posts`
All three tasks implemented strictly in order, TDD (RED -> GREEN) per task, one commit per task.

---

## Task 1: `max_similarity` + multi-face embedding (face.py)

**Implemented:**
- `modules/face.py`: module-level `max_similarity(embeddings, ref_emb)` — max cosine similarity over a list of embeddings, `None` if empty. Added `FaceEngine.all_embeddings(img_data)` (all detected-face embeddings, `[]` if none) and `FaceEngine.max_similarity_to_ref(img_data, ref_emb)` (composes the two). Code transcribed verbatim from brief.

**TDD evidence:**
- RED: `.venv/bin/pytest tests/test_face_agg.py -v` -> `ImportError: cannot import name 'max_similarity' from 'modules.face'` (collection error, 1 error).
- GREEN: `.venv/bin/pytest tests/test_face_agg.py -v` -> `2 passed`.

**Files changed:** `modules/face.py`, `tests/test_face_agg.py` (new).

**Commit:** `ab5b68321dbc157074484fc07082f6880d707dea` — "feat(face): add max_similarity + multi-face embedding extraction"

---

## Task 2: `parse_profile_media` + fetch/download (instagram.py)

**Implemented:**
- `modules/instagram.py`: module-level pure `parse_profile_media(api_json)` — extracts `hd_profile_pic_url_info.url` (falls back to `profile_pic_url`) and post `display_url`/`thumbnail_src` list from a `web_profile_info` response; tolerant of missing `data`/`user`. Added `Instagram.get_profile_media(username)` (in-page fetch of `web_profile_info`, parsed via `parse_profile_media`) and `Instagram.download_image(url)` (paced via `self.rate_limiter.acquire()` + `self.budget.spend()`, then `page.request.get`). Modeled on existing `get_profile_pic` (:413-426 pre-change). Code transcribed verbatim from brief.

**TDD evidence:**
- RED: `.venv/bin/pytest tests/test_profile_media.py -v` -> `ImportError: cannot import name 'parse_profile_media' from 'modules.instagram'` (collection error, 1 error).
- GREEN: `.venv/bin/pytest tests/test_profile_media.py -v` -> `3 passed`.
- Full-suite regression check after this task: `.venv/bin/pytest tests/ -v` -> `21 passed` (no regressions in ratelimit/softblock/config/search_limits tests).

**Files changed:** `modules/instagram.py`, `tests/test_profile_media.py` (new).

**Commit:** `459ac152b05a253c093147a970104b7d7e305a5a` — "feat(instagram): parse profile+post media, add paced download_image (Playwright)"

---

## Task 3: `decide_account` (search.py)

**Implemented:**
- `modules/search.py`: module-level pure `decide_account(image_scores, threshold, consensus_min)` — filters `None` entries, `score` = max of valid scores (`None` if none valid), `matched` = count of valid scores `>= threshold`, `is_match` = `matched >= consensus_min`. Code transcribed verbatim from brief.

**TDD evidence:**
- RED: `.venv/bin/pytest tests/test_decide_account.py -v` -> `ImportError: cannot import name 'decide_account' from 'modules.search'` (collection error, 1 error).
- GREEN: `.venv/bin/pytest tests/test_decide_account.py -v` -> `3 passed`.
- Full-suite regression check after this task: `.venv/bin/pytest tests/ -v` -> `24 passed`.

**Files changed:** `modules/search.py`, `tests/test_decide_account.py` (new).

**Commit:** `3dc3701e5bc7662511c27dedc295cd2976eef951` — "feat(search): add decide_account aggregation (max rank + consensus stop)"

---

## Deviations

None. All three tasks were implemented exactly as specified in their briefs — code, function signatures, and commit messages transcribed verbatim. No ambiguity encountered; no brief required a judgment call.

Pre-existing local modifications to `.superpowers/sdd/progress.md` and the `task-*-brief.md` files (present in `git status` before this work started) were left untouched — out of scope for these tasks and not part of any commit made here.

## Final state

- 3 commits, in order, each scoped to its task's files only.
- Full test suite after all three tasks: `.venv/bin/pytest tests/ -v` -> **24 passed**, pristine output (no warnings/errors).
- Working tree clean w.r.t. `modules/face.py`, `modules/instagram.py`, `modules/search.py`, and the three new test files (all committed).
