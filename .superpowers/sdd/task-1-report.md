# Task 1: Test Harness + Pure Rate-Limit Helpers

## Summary
Bootstrapped pytest test harness and implemented two pure helper functions for rate-limit hardening:
- `jittered_delay(lo, hi, rng=random)` — returns random delay in [lo, hi]
- `backoff_delay(attempt, base=2.0, cap=300.0, rng=random)` — exponential backoff with jitter capped at 300s

## TDD Evidence

### RED (test fails without implementation)
**Command:**
```bash
.venv/bin/pytest tests/test_ratelimit.py -v
```

**Output:**
```
ImportError while importing test module
...
ModuleNotFoundError: No module named 'modules'
```

### GREEN (test passes after implementation)
**Command:**
```bash
.venv/bin/pytest tests/test_ratelimit.py -v
```

**Output:**
```
tests/test_ratelimit.py::test_jittered_delay_within_bounds PASSED        [ 33%]
tests/test_ratelimit.py::test_jittered_delay_zero_range PASSED           [ 66%]
tests/test_ratelimit.py::test_backoff_delay_grows_and_caps PASSED        [100%]

============================== 3 passed in 0.00s ==============================
```

## Files Changed

1. **requirements-dev.txt** (created)
   - Added pytest, pytest-asyncio as dev-only dependencies

2. **pytest.ini** (created)
   - Configured pytest with asyncio_mode=auto and testpaths=tests

3. **modules/ratelimit.py** (created)
   - `jittered_delay()`: uniform random delay bounded by [lo, hi]; returns float(lo) when hi <= lo
   - `backoff_delay()`: exponential backoff formula `base^attempt + uniform(0,1)`, capped at 300s
   - Both functions accept injectable `rng` parameter for determinism in tests

4. **tests/test_ratelimit.py** (created)
   - 3 unit tests covering bounds checking, zero range, growth/saturation behavior

5. **tests/conftest.py** (created)
   - Python path configuration to allow module imports without PYTHONPATH env var

6. **tests/__init__.py** (created)
   - Package marker for tests directory

## Commit
```
cd0b6b0 feat(ratelimit): add pure jitter+backoff helpers with tests
```

## Self-Review

✓ Implements exact signatures from brief  
✓ TDD: wrote tests before code, verified RED/GREEN states  
✓ Pure functions: no side effects, injectable randomness for determinism  
✓ Python 3.9 compatible: no match/type unions, all syntax valid  
✓ Tests pass: 3/3 passing, consistent results with seeded RNG  
✓ Code matches style: minimal docstrings, lowercase function names  

## Concerns
None. Implementation is straightforward and tests are deterministic. The conftest.py addition (not in brief) is necessary for pytest to resolve the modules package without PYTHONPATH.
