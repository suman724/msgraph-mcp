from .auth import OIDCValidator
from .cache import Cache
from .config import settings
from .errors import MCPError


class SessionResolver:
    def __init__(self, cache: Cache, oidc: OIDCValidator) -> None:
        self._cache = cache
        self._oidc = oidc

    async def resolve(self, graph_session_id: str, bearer_token: str) -> dict:
        if not graph_session_id:
            raise MCPError("AUTH_REQUIRED", "Missing session", status=401)
        if not bearer_token:
            if not settings.disable_oidc_validation:
                raise MCPError("AUTH_REQUIRED", "Missing client token", status=401)
        if not settings.disable_oidc_validation and bearer_token:
            await self._oidc.validate(bearer_token)

        cached = self._cache.get_session(graph_session_id)
        if cached:
            cached["session_id"] = graph_session_id
            return cached

        raise MCPError("AUTH_REQUIRED", "Invalid session", status=401)
