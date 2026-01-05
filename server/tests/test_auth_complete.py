import time

import jwt
import pytest

from msgraph_mcp.auth import TokenResponse
from msgraph_mcp.services import AuthService


class FakeCache:
    def __init__(self):
        self.pkce = "verifier"
        self.session = None
        self.access = None

    def pop_pkce(self, _state):
        return self.pkce

    def cache_session(self, session_id, payload):
        self.session = (session_id, payload)

    def cache_access_token(self, session_id, token, expires_in):
        self.access = (session_id, token, expires_in)


class FakeTokenStore:
    def __init__(self):
        self.refresh = None
        self.session = None

    def store_refresh_token(self, tenant_id, user_id, client_id, refresh_token, scopes, expires_at):
        self.refresh = (tenant_id, user_id, client_id, refresh_token, scopes, expires_at)

    def store_session(self, session_id, tenant_id, user_id, client_id, scopes, expires_at):
        self.session = (session_id, tenant_id, user_id, client_id, scopes, expires_at)


class FakeGraph:
    async def request(self, method, url, token, **_kwargs):
        assert method == "GET"
        assert url.endswith("/me")
        return {"id": "user-123"}


@pytest.mark.asyncio
async def test_complete_pkce_stores_session(monkeypatch):
    cache = FakeCache()
    store = FakeTokenStore()
    graph = FakeGraph()
    service = AuthService(cache, store, graph)

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
    assert store.refresh[0] == "tenant-1"
    assert store.session[1] == "tenant-1"
    assert cache.session[1]["user_id"] == "user-123"
