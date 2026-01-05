import base64
from typing import Any

from ..config import settings
from ..errors import MCPError
from ..graph import GraphClient
from ..services import decode_base64_payload


def _pagination_params(pagination: dict | None) -> dict:
    params: dict[str, Any] = {}
    if not pagination:
        return params
    page_size = pagination.get("page_size")
    if page_size:
        params["$top"] = page_size
    cursor = pagination.get("cursor")
    if cursor:
        params["$skiptoken"] = cursor
    return params


def _next_cursor(payload: dict) -> str | None:
    next_link = payload.get("@odata.nextLink")
    if not next_link:
        return None
    if "$skiptoken=" in next_link:
        return next_link.split("$skiptoken=")[-1]
    return None


def _item_url(drive_id: str | None, item_id: str | None, path: str | None) -> str:
    if drive_id and item_id:
        return f"{settings.graph_base_url}/drives/{drive_id}/items/{item_id}"
    if drive_id and path:
        return f"{settings.graph_base_url}/drives/{drive_id}/root:/{path}"
    if item_id:
        return f"{settings.graph_base_url}/me/drive/items/{item_id}"
    if path:
        return f"{settings.graph_base_url}/me/drive/root:/{path}"
    return f"{settings.graph_base_url}/me/drive/root"


async def get_default_drive(graph: GraphClient, token: str) -> dict:
    payload = await graph.request("GET", f"{settings.graph_base_url}/me/drive", token)
    return {"drive": _map_drive(payload)}


async def list_children(graph: GraphClient, token: str, params: dict) -> dict:
    url = _item_url(params.get("drive_id"), params.get("item_id"), params.get("path"))
    payload = await graph.request(
        "GET",
        f"{url}/children",
        token,
        params=_pagination_params(params.get("pagination")),
    )
    return {
        "items": [_map_item(item) for item in payload.get("value", [])],
        "next_cursor": _next_cursor(payload),
    }


async def get_item(graph: GraphClient, token: str, params: dict) -> dict:
    url = _item_url(params.get("drive_id"), params.get("item_id"), params.get("path"))
    payload = await graph.request("GET", url, token)
    return {"item": _map_item(payload)}


async def search(graph: GraphClient, token: str, params: dict) -> dict:
    query = params.get("query")
    if not query:
        raise MCPError("VALIDATION_ERROR", "Query is required")
    path = params.get("path") or "root"
    url = f"{settings.graph_base_url}/me/drive/{path}/search(q='{query}')"
    payload = await graph.request(
        "GET", url, token, params=_pagination_params(params.get("pagination"))
    )
    return {
        "items": [_map_item(item) for item in payload.get("value", [])],
        "next_cursor": _next_cursor(payload),
    }


async def download_file(graph: GraphClient, token: str, params: dict) -> dict:
    url = _item_url(params.get("drive_id"), params.get("item_id"), params.get("path"))
    return_mode = params.get("return_mode", "download_url")

    if return_mode == "download_url":
        payload = await graph.request("GET", url, token)
        return {
            "download_url": payload.get("@microsoft.graph.downloadUrl"),
            "size_bytes": payload.get("size"),
        }

    max_bytes = min(
        params.get("max_bytes", settings.max_base64_bytes), settings.max_base64_bytes
    )
    raw = await graph.request_raw("GET", f"{url}/content", token)
    if len(raw) > max_bytes:
        raise MCPError("VALIDATION_ERROR", "File too large for base64", status=413)
    return {
        "content_base64": base64.b64encode(raw).decode("ascii"),
        "size_bytes": len(raw),
    }


async def upload_small_file(graph: GraphClient, token: str, params: dict) -> dict:
    content = decode_base64_payload(
        params.get("content_base64"), settings.max_base64_bytes
    )
    parent_path = params.get("parent_path", "/").strip("/")
    filename = params.get("filename")
    url = f"{settings.graph_base_url}/me/drive/root:/{parent_path}/{filename}:/content"
    headers = {"Content-Type": "application/octet-stream"}
    payload = await graph.request("PUT", url, token, headers=headers, content=content)
    return {"item": _map_item(payload)}


async def create_upload_session(graph: GraphClient, token: str, params: dict) -> dict:
    parent_path = params.get("parent_path", "/").strip("/")
    filename = params.get("filename")
    url = f"{settings.graph_base_url}/me/drive/root:/{parent_path}/{filename}:/createUploadSession"
    payload = {
        "item": {
            "@microsoft.graph.conflictBehavior": params.get(
                "conflict_behavior", "rename"
            ),
            "name": filename,
        }
    }
    response = await graph.request("POST", url, token, json=payload)
    return {
        "upload_session": {
            "upload_url": response.get("uploadUrl"),
            "expiration_datetime": response.get("expirationDateTime"),
            "next_expected_ranges": response.get("nextExpectedRanges", []),
        }
    }


async def upload_chunk(graph: GraphClient, token: str, params: dict) -> dict:
    upload_url = params.get("upload_url")
    content = decode_base64_payload(
        params.get("content_base64"), settings.max_base64_bytes
    )
    start = params.get("chunk_start")
    end = params.get("chunk_end")
    total = params.get("total_size")
    headers = {"Content-Range": f"bytes {start}-{end}/{total}"}

    response = await graph.request(
        "PUT", upload_url, token, headers=headers, content=content
    )
    return {
        "status": "in_progress" if "nextExpectedRanges" in response else "completed",
        "next_expected_ranges": response.get("nextExpectedRanges", []),
        "item": _map_item(response) if response.get("id") else None,
    }


async def create_folder(graph: GraphClient, token: str, params: dict) -> dict:
    parent_path = params.get("parent_path", "/").strip("/")
    url = f"{settings.graph_base_url}/me/drive/root:/{parent_path}:/children"
    payload = {
        "name": params.get("folder_name"),
        "folder": {},
        "@microsoft.graph.conflictBehavior": params.get("conflict_behavior", "rename"),
    }
    response = await graph.request("POST", url, token, json=payload)
    return {"item": _map_item(response)}


async def delete_item(graph: GraphClient, token: str, params: dict) -> dict:
    url = _item_url(params.get("drive_id"), params.get("item_id"), params.get("path"))
    await graph.request("DELETE", url, token)
    return {"status": "ok"}


async def create_share_link(graph: GraphClient, token: str, params: dict) -> dict:
    url = _item_url(params.get("drive_id"), params.get("item_id"), params.get("path"))
    payload = {
        "type": params.get("link_type", "view"),
        "scope": params.get("scope", "organization"),
    }
    response = await graph.request("POST", f"{url}/createLink", token, json=payload)
    link = response.get("link", {})
    return {
        "link_url": link.get("webUrl"),
        "link_type": link.get("type"),
        "scope": link.get("scope"),
    }


def _map_drive(item: dict) -> dict:
    return {
        "id": item.get("id"),
        "drive_type": item.get("driveType"),
        "owner": item.get("owner", {}).get("user", {}).get("displayName"),
        "web_url": item.get("webUrl"),
    }


def _map_item(item: dict | None) -> dict | None:
    if not item:
        return None
    return {
        "id": item.get("id"),
        "name": item.get("name"),
        "path": item.get("parentReference", {}).get("path"),
        "size_bytes": item.get("size"),
        "is_folder": "folder" in item,
        "mime_type": item.get("file", {}).get("mimeType"),
        "web_url": item.get("webUrl"),
    }
