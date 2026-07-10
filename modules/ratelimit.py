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
