import os
import uuid

from locust import HttpUser, task, between

CLIENT_JWT = os.getenv("MCP_CLIENT_JWT", "")
GRAPH_SESSION_ID = os.getenv("GRAPH_SESSION_ID", "")


def _payload(name: str, arguments: dict) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }


class MCPUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self) -> None:
        self.headers = {"Authorization": f"Bearer {CLIENT_JWT}"}

    @task(3)
    def list_folders(self):
        self.client.post(
            "/mcp",
            json=_payload("mail_list_folders", {"graph_session_id": GRAPH_SESSION_ID}),
            headers=self.headers,
            name="mail_list_folders",
        )

    @task(2)
    def list_messages(self):
        self.client.post(
            "/mcp",
            json=_payload(
                "mail_list_messages",
                {"graph_session_id": GRAPH_SESSION_ID, "pagination": {"page_size": 10}},
            ),
            headers=self.headers,
            name="mail_list_messages",
        )
