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


class SoftBlockError(Exception):
    def __init__(self, kind, detail=""):
        self.kind = kind
        super().__init__(("soft-block: %s %s" % (kind, detail)).strip())


_BODY_MARKERS = [
    ("checkpoint", "checkpoint_required"),
    ("challenge", "challenge_required"),
    ("feedback_required", "feedback_required"),
]


def detect_soft_block(status, url, body_text):
    """Detect account-level soft blocks. 429 (throttle) is intentionally NOT one."""
    if status == 429:
        return None
    if url and "/accounts/login" in url:
        return "login_redirect"
    if body_text:
        low = body_text.lower()
        for kind, marker in _BODY_MARKERS:
            if marker in low:
                return kind
    return None
