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
