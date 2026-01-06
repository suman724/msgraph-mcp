import base64
import hashlib
import json
import secrets
from urllib.parse import urlencode
from dataclasses import dataclass
from typing import Any

import httpx
import jwt
from jwt.algorithms import RSAAlgorithm
import structlog

from .config import settings
from .errors import MCPError

logger = structlog.get_logger(__name__)


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
    params = {
        "client_id": settings.graph_client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "response_mode": "query",
        "scope": scope_str,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    if login_hint:
        params["login_hint"] = login_hint
    query = urlencode(params)
    return (
        f"https://login.microsoftonline.com/{settings.graph_tenant_id}/oauth2/v2.0/authorize"
        f"?{query}"
    )


@dataclass
class TokenResponse:
    access_token: str
    refresh_token: str
    expires_in: int
    scope: str


async def exchange_code_for_token(
    code: str, code_verifier: str, redirect_uri: str, scopes: list[str]
) -> TokenResponse:
    url = f"https://login.microsoftonline.com/{settings.graph_tenant_id}/oauth2/v2.0/token"
    scope_value = " ".join(scopes) if scopes else "offline_access"
    data = {
        "client_id": settings.graph_client_id,
        "scope": scope_value,
        "code": code,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
        "code_verifier": code_verifier,
    }
    if settings.graph_client_secret:
        data["client_secret"] = settings.graph_client_secret
    async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
        response = await client.post(url, data=data)
    if response.status_code >= 400:
        detail = None
        try:
            payload = response.json()
            detail = payload.get("error_description") or payload.get("error")
            if not detail:
                detail = json.dumps(payload)
        except ValueError:
            detail = response.text.strip() or None
        message = "Token exchange failed"
        if detail:
            message = f"{message}: {detail}"
        raise MCPError("UPSTREAM_ERROR", message, status=502)
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
            logger.warning(
                "oidc_jwks_load_failed",
                status=response.status_code,
                url=settings.oidc_jwks_url,
            )
            raise MCPError("AUTH_REQUIRED", "Unable to load JWKS", status=401)
        self._jwks = response.json()
        return self._jwks

    async def validate(self, token: str) -> dict[str, Any]:
        jwks = await self._load_jwks()
        try:
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
            if not kid:
                raise KeyError("Missing kid")
            key = next(k for k in jwks.get("keys", []) if k.get("kid") == kid)
        except StopIteration as exc:  # pragma: no cover - defensive
            logger.warning("oidc_unknown_kid", kid=header.get("kid"))
            raise MCPError("AUTH_REQUIRED", "Unknown key id", status=401) from exc
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("oidc_invalid_header", error=str(exc))
            raise MCPError(
                "AUTH_REQUIRED", f"Invalid token header: {exc}", status=401
            ) from exc
        try:
            jwk_key = RSAAlgorithm.from_jwk(json.dumps(key))
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("oidc_key_decode_failed", error=str(exc))
            raise MCPError(
                "AUTH_REQUIRED", f"Invalid token key: {exc}", status=401
            ) from exc
        try:
            payload = jwt.decode(
                token,
                jwk_key,
                algorithms=["RS256"],
                audience=settings.oidc_audience,
                issuer=settings.oidc_issuer,
            )
            return payload
        except jwt.PyJWTError as exc:
            logger.warning("oidc_invalid_token", error=str(exc))
            raise MCPError(
                "AUTH_REQUIRED", f"Invalid token: {exc}", status=401
            ) from exc
