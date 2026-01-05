from .auth import OIDCValidator
from .cache import RedisCache
from .errors import MCPError
from .token_store import TokenStore


class SessionResolver:
    def __init__(self, cache: RedisCache, token_store: TokenStore, oidc: OIDCValidator) -> None:
        self._cache = cache
        self._token_store = token_store
        self._oidc = oidc

    async def resolve(self, mcp_session_id: str, bearer_token: str) -> dict:
        if not mcp_session_id:
            raise MCPError("AUTH_REQUIRED", "Missing session", status=401)
        if not bearer_token:
            raise MCPError("AUTH_REQUIRED", "Missing client token", status=401)
        await self._oidc.validate(bearer_token)

        cached = self._cache.get_session(mcp_session_id)
        if cached:
            cached["session_id"] = mcp_session_id
            return cached

        session = self._token_store.get_session(mcp_session_id)
        if not session:
            raise MCPError("AUTH_REQUIRED", "Invalid session", status=401)
        session["session_id"] = mcp_session_id
        self._cache.cache_session(mcp_session_id, session)
        return session
