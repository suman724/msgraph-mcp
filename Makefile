.PHONY: help fmt lint test server client load-tests terraform-init terraform-apply terraform-plan

help:
	@echo "Targets:"
	@echo "  fmt            Format Python code (ruff)"
	@echo "  lint           Lint Python code (ruff)"
	@echo "  test           Run Python tests (pytest)"
	@echo "  server         Run MCP server locally"
	@echo "  client         Run sample client"
	@echo "  load-tests     Run Locust load tests"
	@echo "  terraform-init Initialize Terraform"
	@echo "  terraform-plan Plan Terraform"
	@echo "  terraform-apply Apply Terraform"

fmt:
	@cd server && ruff format .

lint:
	@cd server && ruff check .

test:
	@cd server && pytest

server:
	@cd server && python -m msgraph_mcp

client:
	@cd client && python sample_client.py

load-tests:
	@cd load-tests && locust -f locustfile.py --host http://localhost:8080

terraform-init:
	@cd infra/terraform && terraform init

terraform-plan:
	@cd infra/terraform && terraform plan -var-file=env/dev.tfvars

terraform-apply:
	@cd infra/terraform && terraform apply -var-file=env/dev.tfvars
