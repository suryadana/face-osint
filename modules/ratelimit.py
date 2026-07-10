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
