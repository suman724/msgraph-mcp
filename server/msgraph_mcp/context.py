from dataclasses import dataclass


@dataclass
class SessionContext:
    session_id: str
    tenant_id: str
    user_id: str
    client_id: str
    scopes: list[str]
