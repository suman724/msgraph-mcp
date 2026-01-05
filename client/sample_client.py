import os
import uuid

import httpx

BASE_URL = os.getenv("MCP_BASE_URL", "http://localhost:8080/mcp/")
CLIENT_JWT = os.getenv("MCP_CLIENT_JWT", "")
MCP_SESSION_ID = os.getenv("MCP_SESSION_ID", "")


def call_tool(name: str, arguments: dict) -> dict:
    payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }
    headers = {"Authorization": f"Bearer {CLIENT_JWT}"}
    response = httpx.post(BASE_URL, json=payload, headers=headers, timeout=10.0)
    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    result = call_tool(
        "mail_list_folders",
        {"mcp_session_id": MCP_SESSION_ID, "include_hidden": False},
    )
    print(result)
