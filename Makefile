.PHONY: help fmt lint test server client load-tests terraform-init terraform-apply terraform-plan docker-build docker-run ci venv dev-server-run

ROOT_DIR := $(shell pwd)
VENV_BIN := $(ROOT_DIR)/.venv/bin
RUFF := $(if $(wildcard $(VENV_BIN)/ruff),$(VENV_BIN)/ruff,ruff)
PYTEST := $(if $(wildcard $(VENV_BIN)/pytest),$(VENV_BIN)/pytest,pytest)
PYTHON := $(if $(wildcard $(VENV_BIN)/python),$(VENV_BIN)/python,python)

help:
	@echo "Targets:"
	@echo "  venv           Create local virtual environment"
	@echo "  fmt            Format Python code (ruff)"
	@echo "  lint           Lint Python code (ruff)"
	@echo "  test           Run Python tests (pytest)"
	@echo "  server         Run MCP server locally"
	@echo "  client         Run sample MCP client"
	@echo "  load-tests     Run Locust load tests"
	@echo "  docker-build   Build Docker image"
	@echo "  docker-run     Run Docker image"
	@echo "  terraform-init Initialize Terraform"
	@echo "  terraform-plan Plan Terraform"
	@echo "  terraform-apply Apply Terraform"
	@echo "  ci             Run lint + tests"
	@echo "  dev-server-run Run server locally without Redis"

venv:
	@$(PYTHON) -m venv .venv
	@echo "Activate with: source .venv/bin/activate"
	@. .venv/bin/activate && pip install -e server[dev]

fmt:
	@cd server && $(RUFF) format .

lint:
	@cd server && $(RUFF) check .

test:
	@cd server && $(PYTEST)

server:
	@cd server && $(PYTHON) -m msgraph_mcp

dev-server-run:
	@CACHE_MODE=memory \
	GRAPH_CLIENT_ID=$${GRAPH_CLIENT_ID:-local-client} \
	GRAPH_TENANT_ID=$${GRAPH_TENANT_ID:-organizations} \
	GRAPH_REDIRECT_URI=$${GRAPH_REDIRECT_URI:-http://localhost:8080/callback} \
	REDIS_ENDPOINT=$${REDIS_ENDPOINT:-unused} \
	OIDC_ISSUER=$${OIDC_ISSUER:-https://issuer.example.com} \
	OIDC_AUDIENCE=$${OIDC_AUDIENCE:-mcp} \
	OIDC_JWKS_URL=$${OIDC_JWKS_URL:-https://issuer.example.com/.well-known/jwks.json} \
	OTEL_EXPORTER_OTLP_ENDPOINT=$${OTEL_EXPORTER_OTLP_ENDPOINT:-https://otlp.example.com} \
	DATADOG_API_KEY=$${DATADOG_API_KEY:-dev-key} \
	$(PYTHON) -m msgraph_mcp

client:
	@cd client && $(PYTHON) sample_client.py

load-tests:
	@cd load-tests && locust -f locustfile.py --host http://localhost:8080

docker-build:
	@docker build -t msgraph-mcp:local .

docker-run:
	@docker run --rm -p 8080:8080 msgraph-mcp:local

terraform-init:
	@cd infra/terraform && terraform init

terraform-plan:
	@cd infra/terraform && terraform plan -var-file=env/dev.tfvars

terraform-apply:
	@cd infra/terraform && terraform apply -var-file=env/dev.tfvars

ci: lint test
