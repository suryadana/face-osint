import pytest
from modules.ratelimit import SoftBlockError, RateLimiter, RequestBudget
from modules.instagram import Instagram


class _FakeResp:
    def __init__(self, status):
        self.status = status


class _FakePage:
    def __init__(self, final_url, status=200):
        self.url = final_url
        self._status = status
    async def goto(self, url, wait_until="domcontentloaded", timeout=0):
        return _FakeResp(self._status)
    async def evaluate(self, *a, **k):
        return ""


async def test_goto_raises_on_login_redirect():
    ig = Instagram("sessionid=x", rate_limiter=RateLimiter(0), budget=RequestBudget())
    ig.page = _FakePage("https://www.instagram.com/accounts/login/?next=/y/")
    with pytest.raises(SoftBlockError) as ei:
        await ig._goto_with_retry("https://www.instagram.com/y/")
    assert ei.value.kind == "login_redirect"


async def test_goto_ok_returns_response():
    ig = Instagram("sessionid=x", rate_limiter=RateLimiter(0), budget=RequestBudget())
    ig.page = _FakePage("https://www.instagram.com/y/", status=200)
    r = await ig._goto_with_retry("https://www.instagram.com/y/")
    assert r.status == 200
