import json
import os
import threading
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import httpx

BASE_URL = os.getenv("MCP_BASE_URL", "http://localhost:8080/mcp/")
CLIENT_JWT = os.getenv("MCP_CLIENT_JWT", "")
REDIRECT_URI = os.getenv("MCP_REDIRECT_URI", "http://localhost:8000/callback")
SCOPES = [s.strip() for s in os.getenv("MCP_SCOPES", "User.Read").split(",") if s.strip()]


def call_tool(name: str, arguments: dict) -> dict:
    payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }
    headers = {"Authorization": f"Bearer {CLIENT_JWT}"}
    response = httpx.post(BASE_URL, json=payload, headers=headers, timeout=30.0)
    response.raise_for_status()
    data = response.json()
    if "error" in data:
        raise RuntimeError(json.dumps(data["error"], indent=2))
    return data.get("result", data)


class CallbackHandler(BaseHTTPRequestHandler):
    query_params = None
    done_event = None
    callback_path = "/callback"

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != self.callback_path:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")
            return

        CallbackHandler.query_params = {k: v[0] for k, v in parse_qs(parsed.query).items()}

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(
            b"<html><body><h2>Login complete.</h2>"
            b"<p>You can close this window and return to the terminal.</p></body></html>"
        )

        if CallbackHandler.done_event:
            CallbackHandler.done_event.set()

        threading.Thread(target=self.server.shutdown, daemon=True).start()

    def log_message(self, _format, *_args):
        return


def run_local_callback_server(timeout_seconds: int = 300) -> dict:
    parsed = urlparse(REDIRECT_URI)
    host = parsed.hostname or "localhost"
    port = parsed.port or 8000
    CallbackHandler.callback_path = parsed.path or "/callback"

    done = threading.Event()
    CallbackHandler.done_event = done
    CallbackHandler.query_params = None

    httpd = HTTPServer((host, port), CallbackHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    if not done.wait(timeout_seconds):
        httpd.shutdown()
        raise TimeoutError(f"Timed out waiting for OAuth callback on {REDIRECT_URI}")

    return CallbackHandler.query_params or {}


def main() -> None:
    if not CLIENT_JWT:
        raise RuntimeError("MCP_CLIENT_JWT is required for client authentication")

    begin = call_tool("auth_begin_pkce", {"scopes": SCOPES, "redirect_uri": REDIRECT_URI})
    auth_url = begin["authorization_url"]

    print("Open this URL if your browser doesn't open automatically:\n")
    print(auth_url, "\n")
    webbrowser.open(auth_url)

    query_params = run_local_callback_server()
    code = query_params.get("code")
    state = query_params.get("state")
    if not code or not state:
        raise RuntimeError(f"Missing code/state in callback: {query_params}")

    complete = call_tool(
        "auth_complete_pkce",
        {"code": code, "state": state, "redirect_uri": REDIRECT_URI},
    )
    session_id = complete["graph_session_id"]

    profile = call_tool("system_get_profile", {"graph_session_id": session_id})
    print(json.dumps(profile, indent=2))


if __name__ == "__main__":
    main()
