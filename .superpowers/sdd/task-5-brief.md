### Task 5: Config knobs

**Files:**
- Modify: `modules/config.py:16-21` (constants block)

**Interfaces:**
- Produces module constants: `RATE_PER_MIN`, `DELAY_RANGE`, `MAX_REQUESTS`, `MAX_EXPANSIONS_PER_LAYER`, `BACKOFF_CAP`.

- [ ] **Step 1: Write failing test**

Create `tests/test_config.py`:
```python
from modules import config


def test_hardening_defaults_exist():
    assert config.RATE_PER_MIN == 20
    assert config.DELAY_RANGE == (1.0, 3.0)
    assert config.MAX_REQUESTS == 800
    assert config.MAX_EXPANSIONS_PER_LAYER == 15
    assert config.BACKOFF_CAP == 300
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL — `AttributeError: module 'modules.config' has no attribute 'RATE_PER_MIN'`.

- [ ] **Step 3: Add constants**

In `modules/config.py`, after the existing `MAX_DEPTH = 3` line, add:
```python
# --- Rate-limit hardening ---
RATE_PER_MIN = 20                 # global read pace (requests/min); 0 disables
DELAY_RANGE = (1.0, 3.0)          # jittered inter-action delay (seconds)
MAX_REQUESTS = 800                # per-run request budget; None disables
MAX_EXPANSIONS_PER_LAYER = 15     # cap accounts expanded per BFS layer; None disables
BACKOFF_CAP = 300                 # max backoff seconds (was hardcoded 30)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add modules/config.py tests/test_config.py
git commit -m "feat(config): add rate-limit hardening knobs"
```

---

