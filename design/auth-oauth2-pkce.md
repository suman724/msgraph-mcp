# OAuth2 Authorization Code + PKCE

This document defines the delegated OAuth2 flow used by the MCP server to access Microsoft Graph on behalf of end users.

---

## Goals

- Support multi-tenant delegated access via Microsoft Identity Platform.
- Never expose Graph access or refresh tokens to MCP clients.
- Provide a minimal, incremental-consent experience for users.
- Enable centralized policy, auditing, and revocation handling.

---

## Actors

- **MCP Client**: Agentic app calling MCP tools.
- **MCP Server**: PKCE handler and token broker.
- **Microsoft Identity Platform**: OAuth2 authorization server.

---

## Flow summary (PKCE)

1. Client calls `auth_begin_pkce` with requested scopes and a redirect URI.
2. MCP Server generates `code_verifier`, `code_challenge`, and a `state` value.
3. MCP Server returns `authorization_url` and `state` to the client.
4. Client opens browser and user signs in/consents.
5. Microsoft redirects to `redirect_uri` with `code` + `state`.
6. Client calls `auth_complete_pkce` with `code`, `state`, and `redirect_uri`.
7. MCP Server exchanges code for tokens and stores refresh token securely.
8. MCP Server returns a server-managed `mcp_session_id` bound to user + tenant.

**Security**
- Use PKCE S256 only.
- `state` is required to prevent CSRF and must be validated.
- `redirect_uri` must be allowlisted per deployment.

---

## MCP auth tools

### `auth_begin_pkce`

**Purpose**: Start the flow.

**Input schema** (see tool catalog for full JSON):
- `tenant` (default: `organizations`)
- `scopes` (array)
- `redirect_uri`
- `login_hint` (optional)

**Output**:
- `authorization_url`
- `state`
- `code_challenge_method`: `S256`

### `auth_complete_pkce`

**Purpose**: Exchange code for tokens and create a session.

**Input**:
- `code`
- `state`
- `redirect_uri`

**Output**:
- `mcp_session_id`
- `granted_scopes`
- `expires_in`

### `auth_get_status`

**Purpose**: Check if a valid token exists for the session.

**Output**:
- `authenticated` (boolean)
- `granted_scopes`
- `expires_at`

### `auth_logout`

**Purpose**: Remove stored refresh tokens and revoke session.

**Output**:
- `status`: `logged_out`

---

## Token storage and session binding

- Refresh tokens and session metadata are stored in **DynamoDB**.
- Sensitive fields are encrypted with **application-level envelope encryption** (KMS-managed keys).
- **Redis** stores hot session metadata, access tokens, and idempotency keys with TTL.
- Session handle (`mcp_session_id`) maps to a single user + tenant + client_id.

**Never return tokens to MCP clients.** The MCP server is the only token holder.

---

## Scopes and consent strategy

- Start with the minimum delegated scopes required per tool.
- Request additional scopes only when a user first calls a tool requiring them.
- Record granted scopes with a timestamp for auditability.

---

## Error handling

- `AUTH_REQUIRED`: no session or token.
- `CONSENT_REQUIRED`: missing scopes.
- `FORBIDDEN_POLICY`: blocked by policy layer.
- `UPSTREAM_ERROR`: token endpoint failure.

Include `correlation_id` for all auth tool responses.

---

## Operational considerations

- Support token revocation and conditional access changes.
- Use short access token TTLs and refresh on demand.
- Log sign-in failures and consent errors with redacted details.
- Rotate encryption keys regularly and re-wrap tokens on rotation.
