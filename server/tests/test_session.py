import pytest

from msgraph_mcp.errors import MCPError
from msgraph_mcp.session import SessionResolver


class FakeCache:
    def __init__(self):
        self._session = None

    def get_session(self, session_id):
        return self._session


class FakeOIDC:
    async def validate(self, token):
        return {"sub": "caller"}


@pytest.mark.asyncio
async def test_session_resolver_requires_session_id():
    resolver = SessionResolver(FakeCache(), FakeOIDC())
    with pytest.raises(MCPError) as exc:
        await resolver.resolve("", "token")
    assert exc.value.code == "AUTH_REQUIRED"


@pytest.mark.asyncio
async def test_session_resolver_requires_bearer():
    resolver = SessionResolver(FakeCache(), FakeOIDC())
    with pytest.raises(MCPError) as exc:
        await resolver.resolve("session", "")
    assert exc.value.code == "AUTH_REQUIRED"


@pytest.mark.asyncio
async def test_session_resolver_fetches_and_caches_session():
    cache = FakeCache()
    session = {"tenant_id": "t", "user_id": "u", "client_id": "c", "scopes": []}
    cache._session = session
    resolver = SessionResolver(cache, FakeOIDC())

    result = await resolver.resolve("sess-1", "token")

    assert result["session_id"] == "sess-1"
