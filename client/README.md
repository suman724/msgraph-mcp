# Sample MCP Client

This sample uses JSON-RPC calls against the MCP HTTP endpoint. It assumes the server is mounted at `/mcp`.

## Usage

```bash
python sample_client.py
python system_get_profile_client.py
```

Set the following env vars:

- `MCP_BASE_URL` (default: http://localhost:8080/mcp/)
- `MCP_CLIENT_JWT` (required for auth)
- `MCP_REDIRECT_URI` (default: http://localhost:8000/callback)
- `MCP_SCOPES` (default: User.Read; server adds offline_access)
- `GRAPH_SESSION_ID` (required for `sample_client.py` only)

Notes:

- Tool responses are parsed from `structuredContent` when available, with a fallback
  to JSON in `content` for compatibility.
