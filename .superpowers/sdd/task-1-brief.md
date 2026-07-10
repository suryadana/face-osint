### Task 1: Test harness + pure helpers (`jittered_delay`, `backoff_delay`)

**Files:**
- Create: `requirements-dev.txt`
- Create: `pytest.ini`
- Create: `modules/ratelimit.py`
- Test: `tests/test_ratelimit.py`

**Interfaces:**
- Produces:
  - `jittered_delay(lo: float, hi: float, rng=random) -> float`
  - `backoff_delay(attempt: int, base: float = 2.0, cap: float = 300.0, rng=random) -> float`

- [ ] **Step 1: Dev deps + pytest config**

`requirements-dev.txt`:
```
pytest
pytest-asyncio
```

`pytest.ini`:
```ini
[pytest]
asyncio_mode = auto
testpaths = tests
```

Run: `pip install -r requirements-dev.txt`

- [ ] **Step 2: Write failing test**

`tests/test_ratelimit.py`:
```python
import random
from modules.ratelimit import jittered_delay, backoff_delay


def test_jittered_delay_within_bounds():
    rng = random.Random(0)
    for _ in range(100):
        d = jittered_delay(1.0, 3.0, rng=rng)
        assert 1.0 <= d <= 3.0


def test_jittered_delay_zero_range():
    assert jittered_delay(0.0, 0.0) == 0.0


def test_backoff_delay_grows_and_caps():
    seq = [backoff_delay(a, base=2.0, cap=300.0, rng=random.Random(1)) for a in range(12)]
    assert seq[0] < seq[3] < seq[6]         # grows
    assert all(d <= 300.0 for d in seq)     # capped
    assert seq[-1] == 300.0                  # deep attempt saturates cap
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_ratelimit.py -v`
Expected: FAIL — `ModuleNotFoundError` / `ImportError: cannot import name 'jittered_delay'`.

- [ ] **Step 4: Implement helpers**

`modules/ratelimit.py`:
```python
"""Rate-limit hardening primitives (pure + async)."""
import asyncio
import random


def jittered_delay(lo, hi, rng=random):
    """Random delay in [lo, hi]. Returns 0.0 when lo==hi==0."""
    if hi <= lo:
        return float(lo)
    return rng.uniform(lo, hi)


def backoff_delay(attempt, base=2.0, cap=300.0, rng=random):
    """Exponential backoff with jitter, capped at `cap` seconds."""
    return min(base ** attempt + rng.uniform(0, 1), cap)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_ratelimit.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add requirements-dev.txt pytest.ini modules/ratelimit.py tests/test_ratelimit.py
git commit -m "feat(ratelimit): add pure jitter+backoff helpers with tests"
```

---

