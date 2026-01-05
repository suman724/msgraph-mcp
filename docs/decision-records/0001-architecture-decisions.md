# ADR 0001: Core Architecture and Platform Decisions

## Status

Accepted

## Context

We need a production-grade MCP server for Microsoft Graph at ~300K users, deployed on AWS, with high resiliency and performance. The system must support multiple environments and follow the design constraints captured in the project docs.

## Decisions

- Deploy the MCP server as an ECS Fargate service in an existing VPC, ECS cluster, and ALB (internal-only).
- Use a single region (`us-east-1`) initially with four environments: dev, test, preprod, prod.
- Use Redis-only storage for tokens, sessions, and idempotency with TTL-based expiry.
- Store tokens in Redis with TTL-based expiry and app-level encryption; no durable token store.
- Authenticate MCP clients with OIDC JWT (issuer/audience validation via JWKS).
- Use the official MCP Python SDK and Python 3.12 for server implementation.
- Use OpenTelemetry with Datadog as the telemetry backend.
- Use Locust for load testing.
- Limit base64 payloads to 100 MB and use OneDrive upload sessions for large files.
- Do not use WAF; the service is internal-facing only.
- Terraform provisions ECS service and Secrets Manager/KMS, but not VPC/ALB/ECR.

## Consequences

- Infrastructure code assumes existing network and load balancer resources.
- Tokens remain server-side with app-level encryption and controlled access.
- Observability is standardized on OpenTelemetry + Datadog.
- Large file operations require a multi-step upload workflow.
