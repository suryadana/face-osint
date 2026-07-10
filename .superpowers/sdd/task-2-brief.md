### Task 2: `RateLimiter` (global async pacer)

**Files:**
- Modify: `modules/ratelimit.py`
- Test: `tests/test_ratelimit.py`

**Interfaces:**
- Consumes: `jittered_delay`
- Produces: `RateLimiter(rate_per_min, jitter_range=(0.0, 0.0), time_fn=None, sleep_fn=None)` with `async def acquire(self) -> None`. `rate_per_min <= 0` disables pacing (no wait).

- [ ] **Step 1: Write failing test**

Append to `tests/test_ratelimit.py`:
```python
import pytest
from modules.ratelimit import RateLimiter


async def test_rate_limiter_spaces_calls():
    clock = {"t": 0.0}
    slept = []

    def time_fn():
        return clock["t"]

    async def sleep_fn(d):
        slept.append(d)
        clock["t"] += d          # advance virtual clock

    rl = RateLimiter(rate_per_min=60, time_fn=time_fn, sleep_fn=sleep_fn)  # min_interval=1.0s
    await rl.acquire()           # first: no wait
    await rl.acquire()           # second: must wait ~1.0s
    assert slept and abs(slept[-1] - 1.0) < 1e-6


async def test_rate_limiter_disabled():
    slept = []

    async def sleep_fn(d):
        slept.append(d)

    rl = RateLimiter(rate_per_min=0, sleep_fn=sleep_fn)
    await rl.acquire()
    await rl.acquire()
    assert slept == []           # disabled => never sleeps
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ratelimit.py -k rate_limiter -v`
Expected: FAIL — `ImportError: cannot import name 'RateLimiter'`.

- [ ] **Step 3: Implement `RateLimiter`**

Append to `modules/ratelimit.py`:
```python
class RateLimiter:
    """Global pacer: serializes acquire() so requests are >= min_interval apart."""

    def __init__(self, rate_per_min, jitter_range=(0.0, 0.0), time_fn=None, sleep_fn=None):
        self.min_interval = (60.0 / rate_per_min) if rate_per_min and rate_per_min > 0 else 0.0
        self.jitter_range = jitter_range
        self._time = time_fn or (lambda: asyncio.get_event_loop().time())
        self._sleep = sleep_fn or asyncio.sleep
        self._lock = asyncio.Lock()
        self._next_allowed = 0.0

    async def acquire(self):
        if self.min_interval <= 0.0:
            return
        async with self._lock:
            now = self._time()
            wait = self._next_allowed - now
            if wait > 0:
                await self._sleep(wait)
            extra = jittered_delay(*self.jitter_range)
            self._next_allowed = self._time() + self.min_interval + extra
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ratelimit.py -k rate_limiter -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add modules/ratelimit.py tests/test_ratelimit.py
git commit -m "feat(ratelimit): add global RateLimiter with injectable clock"
```

---

