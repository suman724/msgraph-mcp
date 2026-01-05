import base64
import secrets
import time
from dataclasses import dataclass

import httpx
import jwt

from .auth import (
    TokenResponse,
    build_authorization_url,
    exchange_code_for_token,
    generate_pkce_pair,
)
from .cache import Cache
from .config import settings
from .errors import MCPError
from .graph import GraphClient


@dataclass
class AuthBeginResponse:
    authorization_url: str
    state: str


class AuthService:
    def __init__(self, cache: Cache, graph: GraphClient) -> None:
        self._cache = cache
        self._graph = graph

    def begin_pkce(
        self, scopes: list[str], redirect_uri: str | None, login_hint: str | None
    ) -> AuthBeginResponse:
        state = secrets.token_urlsafe(16)
        verifier, challenge = generate_pkce_pair()
        self._cache.cache_pkce(state, verifier)
        url = build_authorization_url(
            scopes,
            state,
            challenge,
            redirect_uri or settings.graph_redirect_uri,
            login_hint,
        )
        return AuthBeginResponse(authorization_url=url, state=state)

    async def complete_pkce(
        self, code: str, state: str, redirect_uri: str | None
    ) -> dict:
        verifier = self._cache.pop_pkce(state)
        if not verifier:
            raise MCPError("AUTH_REQUIRED", "Invalid or expired state", status=401)
        token_response = await exchange_code_for_token(
            code, verifier, redirect_uri or settings.graph_redirect_uri
        )

        claims = jwt.decode(
            token_response.access_token, options={"verify_signature": False}
        )
        tenant_id = claims.get("tid", "unknown")

        me = await self._graph.request(
            "GET", f"{settings.graph_base_url}/me", token_response.access_token
        )
        user_id = me.get("id")
        if not user_id:
            raise MCPError("UPSTREAM_ERROR", "Unable to resolve user", status=502)

        scopes = token_response.scope.split()
        session_id = secrets.token_urlsafe(24)
        expires_at = int(time.time()) + token_response.expires_in

        self._cache.cache_refresh_token(
            session_id, token_response.refresh_token, scopes, expires_at
        )
        self._cache.cache_session_with_expiry(
            session_id,
            {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "client_id": settings.graph_client_id,
                "scopes": scopes,
                "expires_at": expires_at,
            },
            expires_at,
        )
        self._cache.cache_access_token(
            session_id, token_response.access_token, token_response.expires_in
        )

        return {
            "graph_session_id": session_id,
            "granted_scopes": scopes,
            "expires_in": token_response.expires_in,
        }


class TokenService:
    def __init__(self, cache: Cache) -> None:
        self._cache = cache

    async def get_access_token(self, session: dict) -> str:
        cached = self._cache.get_access_token(session["session_id"])
        if cached:
            return cached

        stored = self._cache.get_refresh_token(session["session_id"])
        if not stored or not stored.get("refresh_token"):
            raise MCPError("AUTH_REQUIRED", "No refresh token", status=401)

        token_response = await self._refresh_token(stored["refresh_token"])
        expires_at = int(time.time()) + token_response.expires_in
        self._cache.cache_refresh_token(
            session["session_id"],
            token_response.refresh_token,
            token_response.scope.split(),
            expires_at,
        )
        self._cache.cache_access_token(
            session["session_id"],
            token_response.access_token,
            token_response.expires_in,
        )
        return token_response.access_token

    async def _refresh_token(self, refresh_token: str) -> TokenResponse:
        url = f"https://login.microsoftonline.com/{settings.graph_tenant_id}/oauth2/v2.0/token"
        data = {
            "client_id": settings.graph_client_id,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "scope": "offline_access",
        }
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            response = await client.post(url, data=data)
        if response.status_code >= 400:
            raise MCPError("AUTH_REQUIRED", "Refresh token failed", status=401)
        payload = response.json()
        return TokenResponse(
            access_token=payload["access_token"],
            refresh_token=payload.get("refresh_token", refresh_token),
            expires_in=int(payload["expires_in"]),
            scope=payload.get("scope", ""),
        )


def decode_base64_payload(payload: str, max_bytes: int) -> bytes:
    raw = base64.b64decode(payload)
    if len(raw) > max_bytes:
        raise MCPError("VALIDATION_ERROR", "Payload too large", status=413)
    return raw
