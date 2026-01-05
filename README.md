# MCP Servers for Microsoft Graph (Email, Calendar, OneDrive)

[![CI](https://github.com/suman724/msgraph-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/suman724/msgraph-mcp/actions/workflows/ci.yml)

Design-first project to build **Model Context Protocol (MCP) Servers** that expose **Microsoft Graph** capabilities—**Mail**, **Calendar**, and **OneDrive/Files**—as well-defined MCP tools with clear parameter schemas, production-grade auth, and operational resiliency.

> 📌 **Detailed design docs live in [`design/`](./design/)** (architecture, dataflows, tool catalog, schemas, auth, scaling, resiliency, and references).

---

## Why this exists

We want a clean, production-ready way for **agentic applications** to access Microsoft 365 capabilities through **MCP tools**—with consistent schemas, secure OAuth flows, and a scalable service design suitable for **~300K users**.

---

## Scope

### In-scope
- MCP tool surface for:
  - **Email** (read/search/send/drafts/attachments)
  - **Calendar** (events, availability, create/update/cancel)
  - **OneDrive / Files** (list/search/read/upload/download/share links)
- **OAuth2 Authorization Code + PKCE**
- **Official MCP SDK for Python** for server implementation
- Multi-tenant friendly design (Entra ID)
- Production concerns: rate limits, retries, idempotency, paging, caching, observability, and fault isolation
- Tool schemas designed for agent usability (small, consistent, predictable)

### Out-of-scope (for now)
- Implementing the agentic apps themselves (will come after MCP servers are ready)

---

## Deliverables

1. **Open-source landscape research**
   - Identify relevant open-source MCP servers / Graph integrations and capture GitHub URLs + notes.
2. **Tool catalog + schemas**
   - Define the MCP tools, their descriptions, and parameter/response schemas.
3. **Production design**
   - Auth, tenancy, security model, scaling, resiliency, observability, and operational runbooks.

All of the above are documented in **[`design/`](./design/)**.

---

## Repository structure (proposed)

```
.
├── .github/
│   └── workflows/          # CI
├── design/
│   ├── architecture.md
│   ├── auth-oauth2-pkce.md
│   ├── tool-catalog.md
│   ├── schemas/
│   │   ├── email.tools.json
│   │   ├── calendar.tools.json
│   │   └── onedrive.tools.json
│   ├── resiliency-and-scaling.md
│   ├── operations.md
│   └── appendix-open-source-research.md
├── docs/
│   ├── decision-records/
│   └── glossary.md
├── infra/
│   └── terraform/          # ECS service + Secrets Manager
├── server/                # Python MCP server implementation
├── client/                # sample MCP client
├── load-tests/            # Locust load testing
├── Makefile               # common workflows
├── Dockerfile             # container image
└── README.md              # you are here
```

---

## Quick start (local)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e server
```

Set required env vars (see `server/README.md`), then run:

```bash
make server
```

To run locally without Redis:

```bash
make dev-server-run
```

## CI and tests

```bash
make ci
```

## Terraform (existing VPC/cluster/ALB)

```bash
make terraform-init
make terraform-plan
make terraform-apply
```

Update values in `infra/terraform/env/*.tfvars` before applying.

## Sample client

```bash
make client
```

## Load testing (Locust)

```bash
make load-tests
```
