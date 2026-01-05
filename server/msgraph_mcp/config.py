from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, case_sensitive=False)

    environment: str = "dev"
    aws_region: str = "us-east-1"

    graph_client_id: str
    graph_tenant_id: str = "organizations"
    graph_redirect_uri: str

    cache_mode: str = "redis"
    redis_endpoint: str | None = None
    redis_encryption_key: str | None = None

    oidc_issuer: str
    oidc_audience: str
    oidc_jwks_url: str

    otel_exporter_otlp_endpoint: str
    datadog_api_key: str

    token_cache_ttl_seconds: int = 900
    idempotency_ttl_seconds: int = 1800
    access_token_skew_seconds: int = 300

    max_base64_bytes: int = 100 * 1024 * 1024

    graph_base_url: str = "https://graph.microsoft.com/v1.0"
    http_timeout_seconds: float = 10.0

    max_retry_attempts: int = 4
    retry_base_seconds: float = 0.5

    @model_validator(mode="after")
    def validate_cache_mode(self) -> "Settings":
        if self.cache_mode.lower() == "redis":
            if not self.redis_endpoint:
                raise ValueError("REDIS_ENDPOINT is required when CACHE_MODE=redis")
            if not self.redis_encryption_key:
                raise ValueError(
                    "REDIS_ENCRYPTION_KEY is required when CACHE_MODE=redis"
                )
        return self


settings = Settings()
