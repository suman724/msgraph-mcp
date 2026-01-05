from ..config import settings
from ..graph import GraphClient


async def get_profile(graph: GraphClient, token: str) -> dict:
    params = {"$select": "id,displayName,userPrincipalName,mail"}
    payload = await graph.request(
        "GET", f"{settings.graph_base_url}/me", token, params=params
    )
    return {
        "profile": {
            "id": payload.get("id"),
            "display_name": payload.get("displayName"),
            "user_principal_name": payload.get("userPrincipalName"),
            "mail": payload.get("mail"),
        }
    }
