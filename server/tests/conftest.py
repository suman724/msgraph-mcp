import os


def _set_default(key: str, value: str) -> None:
    os.environ.setdefault(key, value)


_set_default("GRAPH_CLIENT_ID", "test-client")
_set_default("GRAPH_REDIRECT_URI", "http://localhost/callback")
_set_default("REDIS_ENDPOINT", "localhost:6379")
_set_default("DDB_TABLE_TOKENS", "tokens")
_set_default("DDB_TABLE_SESSIONS", "sessions")
_set_default("DDB_TABLE_DELTA", "delta")
_set_default("DDB_TABLE_IDEMPOTENCY", "idempotency")
_set_default("KMS_KEY_ID", "kms-key")
_set_default("OIDC_ISSUER", "https://issuer.example.com")
_set_default("OIDC_AUDIENCE", "mcp")
_set_default("OIDC_JWKS_URL", "https://issuer.example.com/jwks")
_set_default("OTEL_EXPORTER_OTLP_ENDPOINT", "https://otlp.example.com")
_set_default("DATADOG_API_KEY", "dd-key")
