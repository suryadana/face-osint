# Face-Compare from Posts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Naikkan recall + precision face-search dengan mengagregasi wajah dari profile pic + N post terbaru tiap akun.

**Architecture:** Tiga primitif murni (`max_similarity` di face.py, `parse_profile_media` di instagram.py, `decide_account` di search.py) yang unit-testable tanpa model/jaringan, lalu wiring tipis ke `_check_one`. URL post diambil gratis dari respons `web_profile_info` yang sudah dipanggil; tiap download gambar lewat `RateLimiter`+`RequestBudget` dari branch hardening.

**Tech Stack:** Python 3.9/3.11, asyncio, Playwright, numpy, insightface. Test: `pytest` + `pytest-asyncio`.

## Global Constraints

- **Depend pada branch `feat/rate-limit-hardening`** — bangun DI ATAS branch itu (butuh `RateLimiter`, `RequestBudget`, `SoftBlockError` dari `modules/ratelimit.py`). Jangan mulai sebelum branch itu merge/tersedia.
- **Scraping WAJIB Playwright** — download via `page.request.get`, di dalam browser context.
- **Python 3.9 compatible** — no `match`, no `X | Y` runtime unions.
- **Backward compatible** — `POST_SAMPLE_N=0` = perilaku lama (profile-pic-only). Jangan ubah `compare`/`pic`/`scrape`.
- **Defaults (verbatim):** `POST_SAMPLE_N = 3`, `CONSENSUS_MIN = 2`.
- **Aturan match:** skor gambar = max cosine across SEMUA wajah di gambar; `account_score` = max lintas gambar (ranking); auto-stop (`found`) butuh ≥ `CONSENSUS_MIN` gambar berbeda dengan skor ≥ `config.SIM_THRESHOLD`; early-stop download begitu konsensus tercapai.
- **⚠️ TEST COMMAND:** jalankan `.venv/bin/pytest tests/ -v` (python3.11 punya pytest). JANGAN pakai `python -m pytest` — di mesin ini kena rewrite RTK + pyenv 3.9 tak punya pytest → output menyesatkan ("No tests collected").

---

## File Structure

- **Modify** `modules/face.py` — tambah `max_similarity` (pure) + `all_embeddings` + `max_similarity_to_ref`.
- **Modify** `modules/instagram.py` — tambah `parse_profile_media` (pure) + `get_profile_media` + `download_image`.
- **Modify** `modules/search.py` — tambah `decide_account` (pure) + perluas `_check_one`.
- **Modify** `modules/config.py` — `POST_SAMPLE_N`, `CONSENSUS_MIN`.
- **Modify** `face-osint` — flag `--posts N`, teruskan ke `BFSSearch`.
- **Modify** `docs/keamanan-dan-rate-limit.md`, `docs/penggunaan.md` — model volume ×(1+N) + flag baru.
- **Create** `tests/test_face_agg.py`, `tests/test_profile_media.py`, `tests/test_decide_account.py`.

---

### Task 1: `max_similarity` + multi-face embedding (face.py)

**Files:**
- Modify: `modules/face.py`
- Test: `tests/test_face_agg.py`

**Interfaces:**
- Produces:
  - `max_similarity(embeddings, ref_emb) -> float | None` — module-level pure fn; max cosine over a list of embeddings; `None` if list empty.
  - `FaceEngine.all_embeddings(img_data) -> list` — embeddings of ALL detected faces ([] if none).
  - `FaceEngine.max_similarity_to_ref(img_data, ref_emb) -> float | None`.

- [ ] **Step 1: Write failing test**

`tests/test_face_agg.py`:
```python
import numpy as np
from modules.face import max_similarity


def test_max_similarity_picks_best():
    ref = np.array([1.0, 0.0, 0.0])
    embs = [
        np.array([0.0, 1.0, 0.0]),   # cos 0.0
        np.array([1.0, 1.0, 0.0]),   # cos ~0.707
        np.array([2.0, 0.0, 0.0]),   # cos 1.0
    ]
    assert abs(max_similarity(embs, ref) - 1.0) < 1e-6


def test_max_similarity_empty_is_none():
    assert max_similarity([], np.array([1.0, 0.0])) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_face_agg.py -v`
Expected: FAIL — `ImportError: cannot import name 'max_similarity'`.

- [ ] **Step 3: Implement**

In `modules/face.py`, add module-level function (reuse the existing cosine formula):
```python
def max_similarity(embeddings, ref_emb):
    """Max cosine similarity between ref_emb and any embedding in the list. None if empty."""
    best = None
    for emb in embeddings:
        sim = float(ref_emb @ emb / (norm(ref_emb) * norm(emb)))
        if best is None or sim > best:
            best = sim
    return best
```
Add methods to `FaceEngine`:
```python
    def all_embeddings(self, img_data):
        """All face embeddings from raw image bytes (empty list if none)."""
        img = cv2.imdecode(np.frombuffer(img_data, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            return []
        return [f.embedding for f in self.model.get(img)]

    def max_similarity_to_ref(self, img_data, ref_emb):
        """Max similarity of ref_emb to any face found in the image bytes."""
        return max_similarity(self.all_embeddings(img_data), ref_emb)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_face_agg.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add modules/face.py tests/test_face_agg.py
git commit -m "feat(face): add max_similarity + multi-face embedding extraction"
```

---

### Task 2: `parse_profile_media` + fetch/download (instagram.py)

**Files:**
- Modify: `modules/instagram.py`
- Test: `tests/test_profile_media.py`

**Interfaces:**
- Consumes: `RateLimiter`/`RequestBudget` already wired on `Instagram` (from hardening branch).
- Produces:
  - `parse_profile_media(api_json) -> dict` — pure; returns `{"profile_pic_url": str|None, "post_urls": [str, ...]}`.
  - `Instagram.get_profile_media(username) -> dict` — one `web_profile_info` fetch, returns `parse_profile_media(...)`.
  - `Instagram.download_image(url) -> bytes | None` — via `page.request.get`, paced by the limiter/budget.

- [ ] **Step 1: Write failing test**

`tests/test_profile_media.py`:
```python
from modules.instagram import parse_profile_media


def _api(user):
    return {"data": {"user": user}}


def test_parse_extracts_pic_and_posts():
    user = {
        "hd_profile_pic_url_info": {"url": "https://cdn/hd.jpg"},
        "profile_pic_url": "https://cdn/lo.jpg",
        "edge_owner_to_timeline_media": {"edges": [
            {"node": {"display_url": "https://cdn/p1.jpg"}},
            {"node": {"display_url": "https://cdn/p2.jpg"}},
        ]},
    }
    out = parse_profile_media(_api(user))
    assert out["profile_pic_url"] == "https://cdn/hd.jpg"      # hd preferred
    assert out["post_urls"] == ["https://cdn/p1.jpg", "https://cdn/p2.jpg"]


def test_parse_falls_back_to_lo_pic_and_empty_posts():
    out = parse_profile_media(_api({"profile_pic_url": "https://cdn/lo.jpg"}))
    assert out["profile_pic_url"] == "https://cdn/lo.jpg"
    assert out["post_urls"] == []


def test_parse_handles_missing_user():
    out = parse_profile_media({"data": {}})
    assert out == {"profile_pic_url": None, "post_urls": []}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_profile_media.py -v`
Expected: FAIL — `ImportError: cannot import name 'parse_profile_media'`.

- [ ] **Step 3: Implement pure parser**

In `modules/instagram.py`, add module-level function:
```python
def parse_profile_media(api_json):
    """Extract profile pic URL + recent post image URLs from a web_profile_info response."""
    user = ((api_json or {}).get("data") or {}).get("user") or {}
    pic = (user.get("hd_profile_pic_url_info") or {}).get("url") or user.get("profile_pic_url")
    edges = (user.get("edge_owner_to_timeline_media") or {}).get("edges") or []
    posts = []
    for e in edges:
        node = e.get("node") or {}
        u = node.get("display_url") or node.get("thumbnail_src")
        if u:
            posts.append(u)
    return {"profile_pic_url": pic, "post_urls": posts}
```

- [ ] **Step 4: Add `get_profile_media` + `download_image` methods**

Add to the `Instagram` class (model on existing `get_profile_pic` `:396-426`, but return the parsed JSON). The in-page fetch must return the whole `data` object, not just the url:
```python
    async def get_profile_media(self, username):
        if "instagram.com" not in self.page.url:
            try:
                await self.page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=self.timeout)
                await self.page.wait_for_timeout(2000)
            except Exception:
                pass
        raw = await self.page.evaluate(f"""async () => {{
            try {{
                var csrf = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1];
                if(!csrf) return null;
                var r = await fetch('/api/v1/users/web_profile_info/?username={username}', {{
                    headers: {{'X-CSRFToken': csrf, 'X-IG-App-ID': '936619743392459'}}
                }});
                if(!r.ok) return null;
                return await r.json();
            }} catch(e) {{ return null; }}
        }}""")
        if not raw:
            return {"profile_pic_url": None, "post_urls": []}
        return parse_profile_media(raw)

    async def download_image(self, url):
        if not url:
            return None
        await self.rate_limiter.acquire()
        await self.budget.spend()
        resp = await self.page.request.get(url)
        return await resp.body() if resp.ok else None
```

- [ ] **Step 5: Run tests**

Run: `.venv/bin/pytest tests/test_profile_media.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add modules/instagram.py tests/test_profile_media.py
git commit -m "feat(instagram): parse profile+post media, add paced download_image (Playwright)"
```

---

### Task 3: `decide_account` (search.py)

**Files:**
- Modify: `modules/search.py`
- Test: `tests/test_decide_account.py`

**Interfaces:**
- Produces: `decide_account(image_scores, threshold, consensus_min) -> dict` — pure; input list of per-image scores (floats; `None` entries skipped); returns `{"score": float|None, "matched": int, "is_match": bool}` where `score`=max valid (None if none), `matched`=count(score>=threshold), `is_match`=`matched >= consensus_min`.

- [ ] **Step 1: Write failing test**

`tests/test_decide_account.py`:
```python
from modules.search import decide_account


def test_ranking_max_and_consensus_match():
    r = decide_account([0.40, None, 0.38, 0.10], threshold=0.35, consensus_min=2)
    assert abs(r["score"] - 0.40) < 1e-9
    assert r["matched"] == 2
    assert r["is_match"] is True


def test_single_hit_is_not_match_under_consensus():
    r = decide_account([0.50, 0.10, None], threshold=0.35, consensus_min=2)
    assert abs(r["score"] - 0.50) < 1e-9
    assert r["matched"] == 1
    assert r["is_match"] is False


def test_all_none_gives_none_score():
    r = decide_account([None, None], threshold=0.35, consensus_min=2)
    assert r == {"score": None, "matched": 0, "is_match": False}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_decide_account.py -v`
Expected: FAIL — `ImportError: cannot import name 'decide_account'`.

- [ ] **Step 3: Implement**

In `modules/search.py`, add module-level function:
```python
def decide_account(image_scores, threshold, consensus_min):
    """Aggregate per-image scores: max for ranking, consensus (>=consensus_min hits) for match."""
    valid = [s for s in image_scores if s is not None]
    score = max(valid) if valid else None
    matched = sum(1 for s in valid if s >= threshold)
    return {"score": score, "matched": matched, "is_match": matched >= consensus_min}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_decide_account.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add modules/search.py tests/test_decide_account.py
git commit -m "feat(search): add decide_account aggregation (max rank + consensus stop)"
```

---

### Task 4: Wire into `_check_one` + config + CLI + docs

**Files:**
- Modify: `modules/config.py`, `modules/search.py` (`_check_one` `:33-59`, `__init__` `:12-31`), `face-osint` (`cmd_search`)
- Modify: `docs/keamanan-dan-rate-limit.md`, `docs/penggunaan.md`

**Interfaces:**
- Consumes: `get_profile_media`, `download_image`, `FaceEngine.max_similarity_to_ref`, `decide_account`, `config.POST_SAMPLE_N`, `config.CONSENSUS_MIN`, `config.SIM_THRESHOLD`.

- [ ] **Step 1: Add config knobs**

In `modules/config.py`, after existing constants:
```python
# --- Post-image aggregation ---
POST_SAMPLE_N = 3      # recent posts sampled per checked account (0 = profile pic only)
CONSENSUS_MIN = 2      # distinct images >= SIM_THRESHOLD required to auto-stop (FOUND)
```

- [ ] **Step 2: Add `post_n` to BFSSearch + rewrite `_check_one` face logic**

In `BFSSearch.__init__`, add param `post_n=None` and store `self.post_n = config.POST_SAMPLE_N if post_n is None else post_n`.
Replace the face-check core of `_check_one` (`:41-56`) with media aggregation:
```python
                media = await ig.get_profile_media(username)
                pic_url = media["profile_pic_url"]
                if not pic_url:
                    return None
                async with self.lock:
                    if pic_url in self.checked_urls:
                        return None
                    self.checked_urls.add(pic_url)

                scores = []
                pic = await ig.download_image(pic_url)
                if pic is not None:
                    scores.append(self.face.max_similarity_to_ref(pic, self.ref_emb))

                for post_url in media["post_urls"][: self.post_n]:
                    d = decide_account(scores, config.SIM_THRESHOLD, config.CONSENSUS_MIN)
                    if d["is_match"]:
                        break                       # early-stop: consensus already reached
                    img = await ig.download_image(post_url)
                    if img is not None:
                        scores.append(self.face.max_similarity_to_ref(img, self.ref_emb))

                decision = decide_account(scores, config.SIM_THRESHOLD, config.CONSENSUS_MIN)
                if decision["score"] is not None:
                    async with self.lock:
                        self.results.append((username, decision["score"]))
                        self.total_face_checks += 1
                    if decision["is_match"]:
                        self.found.set()
                        self.found_data[0] = (username, decision["score"])
                        return (username, decision["score"])
```
Ensure `decide_account` is imported/defined in the module (Task 3) and `config` is in scope (already imported).

- [ ] **Step 3: CLI flag `--posts`**

In `face-osint` `cmd_search`: add default `post_n = config.POST_SAMPLE_N` near other defaults; in the arg loop add:
```python
        elif args[i] == "--posts" and i + 1 < len(args):
            post_n = int(args[i + 1]); i += 2
```
Pass `post_n=post_n` into the `BFSSearch(...)` constructor. Add a help line:
```python
        print("  --posts N     Recent posts sampled per account (default 3; 0=profile pic only)")
```

- [ ] **Step 4: Manual verification (real run, low volume)**

Run:
```bash
./face-osint --cookie "sessionid=..." search ref.jpg <username> --depth 1 --posts 3 --max-requests 80
```
Expected: per account, downloads profile pic then up to 3 posts (visible), stops sampling an account early once 2 images match, ranks by best score. Compare `--posts 0` (old behavior) vs `--posts 3` on a known account whose profile pic is a logo — the post version should surface a score where the old one detected no face.

- [ ] **Step 5: Update docs**

- `docs/penggunaan.md`: add `--posts N` row to the `search` options table; note aggregation (max rank + consensus stop).
- `docs/keamanan-dan-rate-limit.md`: update the volume model — per checked account cost rises from ~3 requests to ~3 + (1..N) image downloads; note this is bounded by the limiter/budget and the consensus early-stop.

- [ ] **Step 6: Commit**

```bash
git add modules/config.py modules/search.py face-osint docs/penggunaan.md docs/keamanan-dan-rate-limit.md
git commit -m "feat: aggregate profile+post faces in search + --posts flag + docs"
```

---

## Self-Review

**Spec coverage:**
- Robust aggregation (profile+posts) → Task 1 (`max_similarity`, multi-face) + Task 4 (wiring). ✓
- Hybrid sampling N + early-stop → Task 4 (`media["post_urls"][:post_n]`, break on consensus). ✓
- Per-image max across faces → Task 1 (`max_similarity_to_ref`). ✓
- Ranking=max, auto-stop=consensus → Task 3 (`decide_account`). ✓
- Free post URLs from web_profile_info → Task 2 (`get_profile_media` reuses the same fetch). ✓
- Downloads via limiter/budget → Task 2 (`download_image` calls acquire/spend). ✓
- Config `POST_SAMPLE_N`/`CONSENSUS_MIN` + `--posts` → Task 4. ✓
- Volume-model doc update → Task 4 Step 5. ✓
- Backward compat N=0 → Task 4 (`[:post_n]` with post_n=0 → empty; profile-pic-only). ✓

**Placeholder scan:** none — every code step is concrete.

**Type consistency:** `max_similarity(embeddings, ref_emb)` (Task 1) used by `max_similarity_to_ref` (Task 1) and `_check_one` (Task 4). `parse_profile_media`/`get_profile_media` return `{"profile_pic_url","post_urls"}` (Task 2) consumed identically in Task 4. `decide_account(image_scores, threshold, consensus_min) -> {"score","matched","is_match"}` (Task 3) used with those exact keys in Task 4.

**Dependency note:** requires `Instagram` to already carry `rate_limiter`/`budget` (from `feat/rate-limit-hardening` Task 6). This plan must execute on top of that branch.
