### Task 3: `RequestBudget` + `BudgetExceeded`

**Files:**
- Modify: `modules/ratelimit.py`
- Test: `tests/test_ratelimit.py`

**Interfaces:**
- Produces:
  - `class BudgetExceeded(Exception)` with attrs `.spent`, `.limit`.
  - `RequestBudget(max_requests=None)` with `async def spend(self, n=1) -> None` (raises `BudgetExceeded` when total exceeds `max_requests`) and `.spent` int property.

- [ ] **Step 1: Write failing test**

Append to `tests/test_ratelimit.py`:
```python
from modules.ratelimit import RequestBudget, BudgetExceeded


async def test_budget_counts_and_raises():
    b = RequestBudget(max_requests=3)
    await b.spend()          # 1
    await b.spend(2)         # 3 (== limit, still OK)
    assert b.spent == 3
    with pytest.raises(BudgetExceeded) as ei:
        await b.spend()      # 4 > 3
    assert ei.value.limit == 3
    assert ei.value.spent == 4


async def test_budget_unlimited_when_none():
    b = RequestBudget(max_requests=None)
    for _ in range(1000):
        await b.spend()
    assert b.spent == 1000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ratelimit.py -k budget -v`
Expected: FAIL — `ImportError: cannot import name 'RequestBudget'`.

- [ ] **Step 3: Implement**

Append to `modules/ratelimit.py`:
```python
class BudgetExceeded(Exception):
    def __init__(self, spent, limit):
        self.spent = spent
        self.limit = limit
        super().__init__(f"request budget exceeded: {spent} > {limit}")


class RequestBudget:
    """Counts total requests spent across the run; raises when over max_requests."""

    def __init__(self, max_requests=None):
        self.max_requests = max_requests
        self.spent = 0
        self._lock = asyncio.Lock()

    async def spend(self, n=1):
        async with self._lock:
            self.spent += n
            if self.max_requests is not None and self.spent > self.max_requests:
                raise BudgetExceeded(self.spent, self.max_requests)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ratelimit.py -k budget -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add modules/ratelimit.py tests/test_ratelimit.py
git commit -m "feat(ratelimit): add RequestBudget with hard cap"
```

---

