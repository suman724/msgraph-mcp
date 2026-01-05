from msgraph_mcp.cache import RedisCache
from msgraph_mcp.config import settings


class FakeRedis:
    def __init__(self):
        self.calls = []

    def setex(self, key, ttl, payload):
        self.calls.append((key, ttl, payload))


def test_cache_session_with_expiry_uses_skew(monkeypatch):
    settings.access_token_skew_seconds = 300
    cache = RedisCache()
    cache._client = FakeRedis()

    fixed_now = 1_700_000_000
    monkeypatch.setattr(cache, "now", lambda: fixed_now)

    expires_at = fixed_now + 3600

    cache.cache_session_with_expiry("sess", {"a": 1}, expires_at)

    _, ttl, _ = cache._client.calls[0]
    assert ttl == 3600 - 300
