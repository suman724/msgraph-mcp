# MCP Server (Python)

This service implements the Microsoft Graph MCP server using the official MCP Python SDK.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .

export GRAPH_CLIENT_ID="..."
export GRAPH_TENANT_ID="organizations"
export GRAPH_REDIRECT_URI="http://localhost:8080/callback"
export REDIS_ENDPOINT="localhost:6379"
export REDIS_ENCRYPTION_KEY="base64-encoded-32-byte-key"
export OIDC_ISSUER="https://issuer.example.com"
export OIDC_AUDIENCE="mcp"
export OIDC_JWKS_URL="https://issuer.example.com/.well-known/jwks.json"
export OTEL_EXPORTER_OTLP_ENDPOINT="https://api.datadoghq.com/api/v2/otlp"
export DATADOG_API_KEY="..."

uvicorn msgraph_mcp.app:app --host 0.0.0.0 --port 8080
```

## Local run without Redis

```bash
make dev-server-run
```

## Docker

```bash
docker build -t msgraph-mcp:local .
docker run --rm -p 8080:8080 msgraph-mcp:local
```

## Tests

```bash
pytest
```
