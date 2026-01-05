import json
import time

import redis

from .config import settings


class RedisCache:
    def __init__(self) -> None:
        self._client = redis.Redis.from_url(f"redis://{settings.redis_endpoint}")

    def _key(self, prefix: str, value: str) -> str:
        return f"{prefix}:{value}"

    def set_json(self, key: str, payload: dict, ttl_seconds: int) -> None:
        self._client.setex(key, ttl_seconds, json.dumps(payload))

    def get_json(self, key: str) -> dict | None:
        raw = self._client.get(key)
        if not raw:
            return None
        return json.loads(raw)

    def cache_access_token(self, session_id: str, token: str, expires_in: int) -> None:
        ttl = max(expires_in - settings.access_token_skew_seconds, 30)
        self.set_json(self._key("access", session_id), {"token": token}, ttl)

    def get_access_token(self, session_id: str) -> str | None:
        payload = self.get_json(self._key("access", session_id))
        if not payload:
            return None
        return payload.get("token")

    def cache_pkce(self, state: str, verifier: str) -> None:
        self.set_json(self._key("pkce", state), {"verifier": verifier}, 600)

    def pop_pkce(self, state: str) -> str | None:
        key = self._key("pkce", state)
        payload = self.get_json(key)
        if payload:
            self._client.delete(key)
            return payload.get("verifier")
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
