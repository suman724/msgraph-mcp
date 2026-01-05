from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, case_sensitive=False)

    environment: str = "dev"
    aws_region: str = "us-east-1"

    graph_client_id: str
    graph_tenant_id: str = "organizations"
    graph_redirect_uri: str

    redis_endpoint: str

    ddb_table_tokens: str
    ddb_table_sessions: str
    ddb_table_delta: str
    ddb_table_idempotency: str

    kms_key_id: str

    oidc_issuer: str
    oidc_audience: str
    oidc_jwks_url: str

    otel_exporter_otlp_endpoint: str
    datadog_api_key: str

    token_cache_ttl_seconds: int = 900
    idempotency_ttl_seconds: int = 1800
    access_token_skew_seconds: int = 60

    max_base64_bytes: int = 100 * 1024 * 1024

    graph_base_url: str = "https://graph.microsoft.com/v1.0"
    http_timeout_seconds: float = 10.0

    max_retry_attempts: int = 4
    retry_base_seconds: float = 0.5


settings = Settings()
