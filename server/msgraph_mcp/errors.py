from dataclasses import dataclass


@dataclass
class MCPError(Exception):
    code: str
    message: str
    status: int = 400
    correlation_id: str | None = None


def as_error_payload(err: MCPError) -> dict:
    payload = {
        "error": {
            "code": err.code,
            "message": err.message,
        }
    }
    if err.correlation_id:
        payload["error"]["correlation_id"] = err.correlation_id
    return payload
