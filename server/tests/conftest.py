import os


def _set_default(key: str, value: str) -> None:
    os.environ.setdefault(key, value)


_set_default("GRAPH_CLIENT_ID", "test-client")
_set_default("GRAPH_REDIRECT_URI", "http://localhost/callback")
_set_default("REDIS_ENDPOINT", "localhost:6379")
_set_default("REDIS_ENCRYPTION_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
_set_default("OIDC_ISSUER", "https://issuer.example.com")
_set_default("OIDC_AUDIENCE", "mcp")
_set_default("OIDC_JWKS_URL", "https://issuer.example.com/jwks")
_set_default("OTEL_EXPORTER_OTLP_ENDPOINT", "https://otlp.example.com")
_set_default("DATADOG_API_KEY", "dd-key")
