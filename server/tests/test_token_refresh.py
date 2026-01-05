import pytest

from msgraph_mcp.auth import TokenResponse
from msgraph_mcp.services import TokenService


class FakeCache:
    def __init__(self):
        self.cached = None
        self.refresh = None

    def get_access_token(self, _session_id):
        return None

    def cache_access_token(self, session_id, token, expires_in):
        self.cached = (session_id, token, expires_in)

    def get_refresh_token(self, _session_id):
        return {"refresh_token": "rt", "scopes": ["Mail.Read"], "expires_at": 3600}

    def cache_refresh_token(self, session_id, refresh_token, scopes, expires_at):
        self.refresh = (session_id, refresh_token, scopes, expires_at)


@pytest.mark.asyncio
async def test_token_refresh_updates_store_and_cache(monkeypatch):
    cache = FakeCache()
    service = TokenService(cache)

    async def fake_refresh(_):
        return TokenResponse(
            access_token="at", refresh_token="rt2", expires_in=3600, scope="Mail.Read"
        )

    monkeypatch.setattr(service, "_refresh_token", fake_refresh)

    session = {"session_id": "s1", "tenant_id": "t", "user_id": "u", "client_id": "c"}
    token = await service.get_access_token(session)

    assert token == "at"
    assert cache.cached[0] == "s1"
    assert cache.refresh[0] == "s1"
