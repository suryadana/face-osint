### Task 4: `detect_soft_block` + `SoftBlockError`

**Files:**
- Modify: `modules/ratelimit.py`
- Test: `tests/test_ratelimit.py`

**Interfaces:**
- Produces:
  - `class SoftBlockError(Exception)` with attr `.kind`.
  - `detect_soft_block(status: int, url: str, body_text: str) -> str | None` — returns a kind string (`'login_redirect'`, `'checkpoint'`, `'challenge'`, `'feedback_required'`) or `None`. NOTE: HTTP 429 is a *throttle* (handled by backoff), NOT a soft-block, so it returns `None`.

- [ ] **Step 1: Write failing test**

Append to `tests/test_ratelimit.py`:
```python
from modules.ratelimit import detect_soft_block, SoftBlockError


def test_detect_login_redirect():
    assert detect_soft_block(200, "https://www.instagram.com/accounts/login/?next=/x/", "") == "login_redirect"


def test_detect_body_markers():
    assert detect_soft_block(400, "https://www.instagram.com/x/", '{"message":"checkpoint_required"}') == "checkpoint"
    assert detect_soft_block(400, "u", '{"message":"challenge_required"}') == "challenge"
    assert detect_soft_block(400, "u", '{"message":"feedback_required"}') == "feedback_required"


def test_429_is_not_soft_block():
    assert detect_soft_block(429, "https://www.instagram.com/x/", "rate limited") is None


def test_clean_response_is_none():
    assert detect_soft_block(200, "https://www.instagram.com/x/", '{"data":{"user":{}}}') is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ratelimit.py -k "soft or detect or 429 or clean" -v`
Expected: FAIL — `ImportError: cannot import name 'detect_soft_block'`.

- [ ] **Step 3: Implement**

Append to `modules/ratelimit.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ratelimit.py -k "soft or detect or 429 or clean" -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add modules/ratelimit.py tests/test_ratelimit.py
git commit -m "feat(ratelimit): add soft-block detection + SoftBlockError"
```

---

