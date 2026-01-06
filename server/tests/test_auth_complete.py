import jwt
import pytest

from msgraph_mcp.auth import TokenResponse
from msgraph_mcp.services import AuthService


class FakeCache:
    def __init__(self):
        self.pkce = {
            "verifier": "verifier",
            "scopes": ["Mail.Read", "offline_access"],
            "redirect_uri": "http://localhost/callback",
        }
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

    async def fake_exchange(_code, _verifier, _redirect_uri, _scopes):
        return TokenResponse(
            access_token=access_token,
            refresh_token="refresh",
            expires_in=3600,
            scope="Mail.Read",
        )

    monkeypatch.setattr("msgraph_mcp.services.exchange_code_for_token", fake_exchange)

    result = await service.complete_pkce("code", "state", "http://localhost/callback")

    assert "graph_session_id" in result
    assert cache.session[1]["user_id"] == "user-123"
    assert cache.refresh[1] == "refresh"


@pytest.mark.asyncio
async def test_complete_pkce_uses_cached_redirect_uri_and_scopes(monkeypatch):
    cache = FakeCache()
    cache.pkce = {
        "verifier": "verifier",
        "scopes": ["Mail.Read", "offline_access"],
        "redirect_uri": "http://stored/callback",
    }
    graph = FakeGraph()
    service = AuthService(cache, graph)

    access_token = jwt.encode({"tid": "tenant-1"}, "secret", algorithm="HS256")
    captured = {}

    async def fake_exchange(code, verifier, redirect_uri, scopes):
        captured["code"] = code
        captured["verifier"] = verifier
        captured["redirect_uri"] = redirect_uri
        captured["scopes"] = scopes
        return TokenResponse(
            access_token=access_token,
            refresh_token="refresh",
            expires_in=3600,
            scope="Mail.Read offline_access",
        )

    monkeypatch.setattr("msgraph_mcp.services.exchange_code_for_token", fake_exchange)

    await service.complete_pkce("code", "state", None)

    assert captured["redirect_uri"] == "http://stored/callback"
    assert captured["scopes"] == ["Mail.Read", "offline_access"]
