import os
from mcp_client import call_tool

BASE_URL = os.getenv("MCP_BASE_URL", "http://localhost:8080/mcp/")
CLIENT_JWT = os.getenv("MCP_CLIENT_JWT", "")
GRAPH_SESSION_ID = os.getenv("GRAPH_SESSION_ID", "")


if __name__ == "__main__":
    if not CLIENT_JWT:
        raise RuntimeError("MCP_CLIENT_JWT is required for client authentication")
    if not GRAPH_SESSION_ID:
        raise RuntimeError("GRAPH_SESSION_ID is required to run this sample")
    result = call_tool(
        BASE_URL,
        CLIENT_JWT,
        "mail_list_folders",
        {"graph_session_id": GRAPH_SESSION_ID, "include_hidden": False},
        timeout=10.0,
    )
    print(result)
