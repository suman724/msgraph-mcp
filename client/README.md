# Sample MCP Client

This sample uses JSON-RPC calls against the MCP HTTP endpoint. It assumes the server is mounted at `/mcp`.

## Usage

```bash
python sample_client.py
python system_get_profile_client.py
```

Set the following env vars:

- `MCP_BASE_URL` (default: http://localhost:8080/mcp)
- `MCP_CLIENT_JWT`
- `MCP_SESSION_ID`
