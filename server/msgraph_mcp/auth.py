import base64
import hashlib
import secrets
from dataclasses import dataclass
from typing import Any

import httpx
import jwt

from .config import settings
from .errors import MCPError


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def generate_pkce_pair() -> tuple[str, str]:
    verifier = _b64url_encode(secrets.token_bytes(32))
    challenge = _b64url_encode(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


def build_authorization_url(
    scopes: list[str],
    state: str,
    code_challenge: str,
    redirect_uri: str,
    login_hint: str | None,
) -> str:
    scope_str = " ".join(scopes)
    url = (
        f"https://login.microsoftonline.com/{settings.graph_tenant_id}/oauth2/v2.0/authorize"
        f"?client_id={settings.graph_client_id}"
        f"&response_type=code"
        f"&redirect_uri={redirect_uri}"
        f"&response_mode=query"
        f"&scope={scope_str}"
        f"&state={state}"
        f"&code_challenge={code_challenge}"
        f"&code_challenge_method=S256"
    )
    if login_hint:
        url = f"{url}&login_hint={login_hint}"
    return url


@dataclass
class TokenResponse:
    access_token: str
    refresh_token: str
    expires_in: int
    scope: str


async def exchange_code_for_token(
    code: str, code_verifier: str, redirect_uri: str
) -> TokenResponse:
    url = f"https://login.microsoftonline.com/{settings.graph_tenant_id}/oauth2/v2.0/token"
    data = {
        "client_id": settings.graph_client_id,
        "scope": "offline_access",
        "code": code,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
        "code_verifier": code_verifier,
    }
    async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
        response = await client.post(url, data=data)
    if response.status_code >= 400:
        raise MCPError("UPSTREAM_ERROR", "Token exchange failed", status=502)
    payload = response.json()
    return TokenResponse(
        access_token=payload["access_token"],
        refresh_token=payload["refresh_token"],
        expires_in=int(payload["expires_in"]),
        scope=payload.get("scope", ""),
    )


class OIDCValidator:
    def __init__(self) -> None:
        self._jwks: dict[str, Any] | None = None

    async def _load_jwks(self) -> dict[str, Any]:
        if self._jwks:
            return self._jwks
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            response = await client.get(settings.oidc_jwks_url)
        if response.status_code >= 400:
            raise MCPError("AUTH_REQUIRED", "Unable to load JWKS", status=401)
        self._jwks = response.json()
        return self._jwks

    async def validate(self, token: str) -> dict[str, Any]:
        jwks = await self._load_jwks()
        try:
            header = jwt.get_unverified_header(token)
            key = next(k for k in jwks["keys"] if k["kid"] == header["kid"])
        except Exception as exc:  # pragma: no cover - defensive
            raise MCPError("AUTH_REQUIRED", "Invalid token header", status=401) from exc
        try:
            payload = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience=settings.oidc_audience,
                issuer=settings.oidc_issuer,
            )
            return payload
        except jwt.PyJWTError as exc:
            raise MCPError("AUTH_REQUIRED", "Invalid token", status=401) from exc
