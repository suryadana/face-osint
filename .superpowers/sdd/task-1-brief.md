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

