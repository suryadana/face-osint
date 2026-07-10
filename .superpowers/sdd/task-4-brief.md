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
