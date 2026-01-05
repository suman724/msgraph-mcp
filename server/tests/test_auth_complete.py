import jwt
import pytest

from msgraph_mcp.auth import TokenResponse
from msgraph_mcp.services import AuthService


class FakeCache:
    def __init__(self):
        self.pkce = "verifier"
        self.session = None
        self.access = None
        self.refresh = None

    def pop_pkce(self, _state):
        return self.pkce

    def cache_session_with_expiry(self, session_id, payload, _expires_at):
        self.session = (session_id, payload)

    def cache_access_token(self, session_id, token, expires_in):
        self.access = (session_id, token, expires_in)

    def cache_refresh_token(self, session_id, refresh_token, scopes, expires_at):
        self.refresh = (session_id, refresh_token, scopes, expires_at)


class FakeGraph:
    async def request(self, method, url, token, **_kwargs):
        assert method == "GET"
        assert url.endswith("/me")
        return {"id": "user-123"}


@pytest.mark.asyncio
async def test_complete_pkce_stores_session(monkeypatch):
    cache = FakeCache()
    graph = FakeGraph()
    service = AuthService(cache, graph)

    access_token = jwt.encode({"tid": "tenant-1"}, "secret", algorithm="HS256")

    async def fake_exchange(_code, _verifier, _redirect_uri):
        return TokenResponse(
            access_token=access_token,
            refresh_token="refresh",
            expires_in=3600,
            scope="Mail.Read",
        )

    monkeypatch.setattr("msgraph_mcp.services.exchange_code_for_token", fake_exchange)

    result = await service.complete_pkce("code", "state", "http://localhost/callback")

    assert "mcp_session_id" in result
    assert cache.session[1]["user_id"] == "user-123"
    assert cache.refresh[1] == "refresh"
