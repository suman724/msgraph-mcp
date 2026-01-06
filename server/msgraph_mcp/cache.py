import base64
import json
import os
import time
from typing import Protocol

import redis
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .config import settings


class Cache(Protocol):
    def cache_access_token(
        self, session_id: str, token: str, expires_in: int
    ) -> None: ...

    def get_access_token(self, session_id: str) -> str | None: ...

    def cache_pkce(
        self, state: str, verifier: str, scopes: list[str], redirect_uri: str
    ) -> None: ...

    def pop_pkce(self, state: str) -> dict | None: ...

    def cache_session_with_expiry(
        self, session_id: str, payload: dict, expires_at: int
    ) -> None: ...

    def get_session(self, session_id: str) -> dict | None: ...

    def delete_session(self, session_id: str) -> None: ...

    def cache_refresh_token(
        self, session_id: str, refresh_token: str, scopes: list[str], expires_at: int
    ) -> None: ...

    def get_refresh_token(self, session_id: str) -> dict | None: ...

    def delete_refresh_token(self, session_id: str) -> None: ...

    def cache_idempotency(self, key: str, payload: dict) -> None: ...

    def get_idempotency(self, key: str) -> dict | None: ...

    def record_rate_limit(self, key: str, tokens: int, ttl_seconds: int) -> None: ...

    def get_rate_limit(self, key: str) -> int | None: ...

    def now(self) -> int: ...


class RedisCache:
    def __init__(self) -> None:
        self._client = redis.Redis.from_url(f"redis://{settings.redis_endpoint}")
        key = base64.b64decode(settings.redis_encryption_key)
        if len(key) != 32:
            raise ValueError("REDIS_ENCRYPTION_KEY must be 32 bytes (base64-encoded)")
        self._aesgcm = AESGCM(key)

    def _key(self, prefix: str, value: str) -> str:
        return f"{prefix}:{value}"

    def set_json(self, key: str, payload: dict, ttl_seconds: int) -> None:
        plaintext = json.dumps(payload).encode("utf-8")
        encrypted = self._encrypt(plaintext)
        self._client.setex(key, ttl_seconds, encrypted)

    def get_json(self, key: str) -> dict | None:
        raw = self._client.get(key)
        if not raw:
            return None
        plaintext = self._decrypt(raw.decode("ascii"))
        return json.loads(plaintext.decode("utf-8"))

    def cache_access_token(self, session_id: str, token: str, expires_in: int) -> None:
        ttl = max(expires_in - settings.access_token_skew_seconds, 30)
        self.set_json(self._key("access", session_id), {"token": token}, ttl)

    def get_access_token(self, session_id: str) -> str | None:
        payload = self.get_json(self._key("access", session_id))
        if not payload:
            return None
        return payload.get("token")

    def cache_pkce(
        self, state: str, verifier: str, scopes: list[str], redirect_uri: str
    ) -> None:
        self.set_json(
            self._key("pkce", state),
            {"verifier": verifier, "scopes": scopes, "redirect_uri": redirect_uri},
            600,
        )

    def pop_pkce(self, state: str) -> dict | None:
        key = self._key("pkce", state)
        payload = self.get_json(key)
        if payload:
            self._client.delete(key)
            verifier = payload.get("verifier")
            if not verifier:
                return None
            return {
                "verifier": verifier,
                "scopes": payload.get("scopes") or [],
                "redirect_uri": payload.get("redirect_uri"),
            }
        return None

    def cache_session(self, session_id: str, payload: dict) -> None:
        self.set_json(
            self._key("session", session_id), payload, settings.token_cache_ttl_seconds
        )

    def get_session(self, session_id: str) -> dict | None:
        return self.get_json(self._key("session", session_id))

    def cache_session_with_expiry(
        self, session_id: str, payload: dict, expires_at: int
    ) -> None:
        ttl = self._ttl_from_expires_at(expires_at)
        self.set_json(self._key("session", session_id), payload, ttl)

    def delete_session(self, session_id: str) -> None:
        self._client.delete(self._key("session", session_id))

    def cache_refresh_token(
        self, session_id: str, refresh_token: str, scopes: list[str], expires_at: int
    ) -> None:
        ttl = self._ttl_from_expires_at(expires_at)
        self.set_json(
            self._key("refresh", session_id),
            {
                "refresh_token": refresh_token,
                "scopes": scopes,
                "expires_at": expires_at,
            },
            ttl,
        )

    def get_refresh_token(self, session_id: str) -> dict | None:
        return self.get_json(self._key("refresh", session_id))

    def delete_refresh_token(self, session_id: str) -> None:
        self._client.delete(self._key("refresh", session_id))

    def cache_idempotency(self, key: str, payload: dict) -> None:
        self.set_json(
            self._key("idempotency", key), payload, settings.idempotency_ttl_seconds
        )

    def get_idempotency(self, key: str) -> dict | None:
        return self.get_json(self._key("idempotency", key))

    def record_rate_limit(self, key: str, tokens: int, ttl_seconds: int) -> None:
        self._client.setex(self._key("rate", key), ttl_seconds, str(tokens))

    def get_rate_limit(self, key: str) -> int | None:
        value = self._client.get(self._key("rate", key))
        if value is None:
            return None
        return int(value)

    def now(self) -> int:
        return int(time.time())

    def _ttl_from_expires_at(self, expires_at: int) -> int:
        ttl = max(expires_at - self.now() - settings.access_token_skew_seconds, 30)
        return ttl

    def _encrypt(self, plaintext: bytes) -> str:
        nonce = os.urandom(12)
        ciphertext = self._aesgcm.encrypt(nonce, plaintext, None)
        return base64.b64encode(nonce + ciphertext).decode("ascii")

    def _decrypt(self, payload: str) -> bytes:
        raw = base64.b64decode(payload)
        if len(raw) < 13:
            raise ValueError("Invalid encrypted payload")
        nonce = raw[:12]
        ciphertext = raw[12:]
        return self._aesgcm.decrypt(nonce, ciphertext, None)


class InMemoryCache:
    def __init__(self) -> None:
        self._store: dict[str, tuple[int, dict]] = {}

    def _key(self, prefix: str, value: str) -> str:
        return f"{prefix}:{value}"

    def _set(self, key: str, payload: dict, ttl_seconds: int) -> None:
        self._store[key] = (self.now() + ttl_seconds, payload)

    def _get(self, key: str) -> dict | None:
        entry = self._store.get(key)
        if not entry:
            return None
        expires_at, payload = entry
        if self.now() >= expires_at:
            self._store.pop(key, None)
            return None
        return payload

    def cache_access_token(self, session_id: str, token: str, expires_in: int) -> None:
        ttl = max(expires_in - settings.access_token_skew_seconds, 30)
        self._set(self._key("access", session_id), {"token": token}, ttl)

    def get_access_token(self, session_id: str) -> str | None:
        payload = self._get(self._key("access", session_id))
        if not payload:
            return None
        return payload.get("token")

    def cache_pkce(
        self, state: str, verifier: str, scopes: list[str], redirect_uri: str
    ) -> None:
        self._set(
            self._key("pkce", state),
            {"verifier": verifier, "scopes": scopes, "redirect_uri": redirect_uri},
            600,
        )

    def pop_pkce(self, state: str) -> dict | None:
        key = self._key("pkce", state)
        payload = self._get(key)
        if payload:
            self._store.pop(key, None)
            verifier = payload.get("verifier")
            if not verifier:
                return None
            return {
                "verifier": verifier,
                "scopes": payload.get("scopes") or [],
                "redirect_uri": payload.get("redirect_uri"),
            }
        return None

    def cache_session_with_expiry(
        self, session_id: str, payload: dict, expires_at: int
    ) -> None:
        ttl = self._ttl_from_expires_at(expires_at)
        self._set(self._key("session", session_id), payload, ttl)

    def get_session(self, session_id: str) -> dict | None:
        return self._get(self._key("session", session_id))

    def delete_session(self, session_id: str) -> None:
        self._store.pop(self._key("session", session_id), None)

    def cache_refresh_token(
        self, session_id: str, refresh_token: str, scopes: list[str], expires_at: int
    ) -> None:
        ttl = self._ttl_from_expires_at(expires_at)
        self._set(
            self._key("refresh", session_id),
            {
                "refresh_token": refresh_token,
                "scopes": scopes,
                "expires_at": expires_at,
            },
            ttl,
        )

    def get_refresh_token(self, session_id: str) -> dict | None:
        return self._get(self._key("refresh", session_id))

    def delete_refresh_token(self, session_id: str) -> None:
        self._store.pop(self._key("refresh", session_id), None)

    def cache_idempotency(self, key: str, payload: dict) -> None:
        self._set(
            self._key("idempotency", key), payload, settings.idempotency_ttl_seconds
        )

    def get_idempotency(self, key: str) -> dict | None:
        return self._get(self._key("idempotency", key))

    def record_rate_limit(self, key: str, tokens: int, ttl_seconds: int) -> None:
        self._set(self._key("rate", key), {"tokens": tokens}, ttl_seconds)

    def get_rate_limit(self, key: str) -> int | None:
        payload = self._get(self._key("rate", key))
        if not payload:
            return None
        return int(payload.get("tokens", 0))

    def now(self) -> int:
        return int(time.time())

    def _ttl_from_expires_at(self, expires_at: int) -> int:
        return max(expires_at - self.now() - settings.access_token_skew_seconds, 30)


def create_cache() -> Cache:
    if settings.cache_mode.lower() == "memory":
        return InMemoryCache()
    return RedisCache()
