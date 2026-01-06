import json
import uuid
from typing import Any

import httpx

MCP_ACCEPT = "application/json, text/event-stream"


def _parse_text_content(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _tool_error_message(result: dict[str, Any]) -> str:
    content = result.get("content") or []
    if content:
        first = content[0]
        if isinstance(first, dict) and first.get("type") == "text":
            return first.get("text", "Unknown MCP tool error")
    return "Unknown MCP tool error"


def _normalize_tool_result(result: dict[str, Any]) -> Any:
    if result.get("isError"):
        raise RuntimeError(_tool_error_message(result))

    structured = result.get("structuredContent")
    if structured is not None:
        return structured

    content = result.get("content") or []
    if content:
        first = content[0]
        if isinstance(first, dict) and first.get("type") == "text":
            return _parse_text_content(first.get("text", ""))

    return result


def call_tool(
    base_url: str,
    client_jwt: str,
    name: str,
    arguments: dict[str, Any],
    *,
    timeout: float = 30.0,
) -> Any:
    payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }
    headers = {"Authorization": f"Bearer {client_jwt}", "Accept": MCP_ACCEPT}
    response = httpx.post(base_url, json=payload, headers=headers, timeout=timeout)
    response.raise_for_status()
    data = response.json()
    if "error" in data:
        raise RuntimeError(json.dumps(data["error"], indent=2))
    result = data.get("result", data)
    if isinstance(result, dict) and ("content" in result or "structuredContent" in result):
        return _normalize_tool_result(result)
    return result
