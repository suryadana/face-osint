### Task 7: Enforce cap + graceful stop in `search.py`

**Files:**
- Modify: `modules/search.py` (constructor `:12-31`, `_check_one` `:33-59`, `search` `:61-142`)
- Test: `tests/test_search_limits.py`

**Interfaces:**
- Consumes: `RateLimiter`, `RequestBudget`, `BudgetExceeded`, `SoftBlockError`, `config.MAX_EXPANSIONS_PER_LAYER`.
- Produces: `BFSSearch(..., rate_limiter=None, budget=None)` stores them and passes into every `Instagram(...)`. New attrs `self.stopped` (`asyncio.Event`) + `self.stop_reason` (str|None). Expansion loop slices candidates to `config.MAX_EXPANSIONS_PER_LAYER`.

- [ ] **Step 1: Write failing test (fake expansion cap)**

`tests/test_search_limits.py`:
```python
from modules import config
from modules.search import cap_expansions


def test_cap_expansions_limits_count():
    users = [f"u{i}" for i in range(50)]
    assert cap_expansions(users, 15) == users[:15]


def test_cap_expansions_none_disables():
    users = ["a", "b", "c"]
    assert cap_expansions(users, None) == users
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_search_limits.py -v`
Expected: FAIL — `ImportError: cannot import name 'cap_expansions'`.

- [ ] **Step 3: Add `cap_expansions` helper + inject limits**

In `modules/search.py`, add module-level helper:
```python
def cap_expansions(candidates, max_per_layer):
    """Return at most max_per_layer candidates (None => no cap)."""
    if max_per_layer is None:
        return list(candidates)
    return list(candidates)[:max_per_layer]
```
Extend `BFSSearch.__init__` to accept and store `rate_limiter=None, budget=None`, and add:
```python
        self.rate_limiter = rate_limiter
        self.budget = budget
        self.stopped = asyncio.Event()
        self.stop_reason = None
```
In `_check_one` (`:40`) and the expansion `Instagram(...)` (`:119`), pass `rate_limiter=self.rate_limiter, budget=self.budget`. Wrap the bodies so `SoftBlockError`/`BudgetExceeded` set stop:
```python
        except (SoftBlockError, BudgetExceeded) as e:
            self.stop_reason = str(e)
            self.stopped.set()
            self.found.set()   # reuse existing short-circuit to unwind everything
            return None
```
Import at top: `from modules.ratelimit import SoftBlockError, BudgetExceeded`.

- [ ] **Step 4: Apply expansion cap in `search`**

In `search` (`:104`), after building `expand`, insert:
```python
        expand = cap_expansions(expand, config.MAX_EXPANSIONS_PER_LAYER)
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_search_limits.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add modules/search.py tests/test_search_limits.py
git commit -m "feat(search): cap expansions per layer + graceful stop on soft-block/budget"
```

---

