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

