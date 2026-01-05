from typing import Any

from ..config import settings
from ..errors import MCPError
from ..graph import GraphClient


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


async def list_folders(
    graph: GraphClient, token: str, include_hidden: bool, pagination: dict | None
) -> dict:
    params = _pagination_params(pagination)
    if not include_hidden:
        params["$filter"] = "isHidden eq false"
    payload = await graph.request(
        "GET", f"{settings.graph_base_url}/me/mailFolders", token, params=params
    )
    return {
        "items": [
            {
                "id": item.get("id"),
                "display_name": item.get("displayName"),
                "parent_folder_id": item.get("parentFolderId"),
                "total_item_count": item.get("totalItemCount"),
                "unread_item_count": item.get("unreadItemCount"),
            }
            for item in payload.get("value", [])
        ],
        "next_cursor": _next_cursor(payload),
    }


async def list_messages(graph: GraphClient, token: str, params: dict) -> dict:
    pagination = params.get("pagination")
    query_params = _pagination_params(pagination)

    if params.get("folder_id"):
        url = f"{settings.graph_base_url}/me/mailFolders/{params['folder_id']}/messages"
    else:
        url = f"{settings.graph_base_url}/me/messages"

    filters = []
    if params.get("from_datetime"):
        filters.append(f"receivedDateTime ge {params['from_datetime']}")
    if params.get("to_datetime"):
        filters.append(f"receivedDateTime le {params['to_datetime']}")
    if params.get("unread_only"):
        filters.append("isRead eq false")
    if filters:
        query_params["$filter"] = " and ".join(filters)

    select_fields = params.get("select_fields")
    if select_fields:
        query_params["$select"] = ",".join(select_fields)

    payload = await graph.request("GET", url, token, params=query_params)
    return {
        "items": [
            {
                "id": item.get("id"),
                "subject": item.get("subject"),
                "from": _map_recipient(item.get("from")),
                "received_datetime": item.get("receivedDateTime"),
                "is_read": item.get("isRead"),
                "has_attachments": item.get("hasAttachments"),
            }
            for item in payload.get("value", [])
        ],
        "next_cursor": _next_cursor(payload),
    }


async def get_message(
    graph: GraphClient,
    token: str,
    message_id: str,
    include_body: bool,
    include_attachments: bool,
) -> dict:
    params = {}
    select_fields = [
        "id",
        "subject",
        "from",
        "toRecipients",
        "ccRecipients",
        "bccRecipients",
        "receivedDateTime",
    ]
    if include_body:
        select_fields.append("body")
    if include_attachments:
        select_fields.append("attachments")
    params["$select"] = ",".join(select_fields)

    payload = await graph.request(
        "GET",
        f"{settings.graph_base_url}/me/messages/{message_id}",
        token,
        params=params,
    )
    return {
        "message": {
            "id": payload.get("id"),
            "subject": payload.get("subject"),
            "from": _map_recipient(payload.get("from")),
            "to": [_map_recipient(r) for r in payload.get("toRecipients", [])],
            "cc": [_map_recipient(r) for r in payload.get("ccRecipients", [])],
            "bcc": [_map_recipient(r) for r in payload.get("bccRecipients", [])],
            "received_datetime": payload.get("receivedDateTime"),
            "body": _map_body(payload.get("body")),
            "attachments": [_map_attachment(a) for a in payload.get("attachments", [])],
        }
    }


async def search_messages(graph: GraphClient, token: str, params: dict) -> dict:
    query = params.get("query")
    if not query:
        raise MCPError("VALIDATION_ERROR", "Query is required")
    query_params = {"$search": f'"{query}"', "$count": "true"}
    query_params.update(_pagination_params(params.get("pagination")))

    headers = {"ConsistencyLevel": "eventual"}
    payload = await graph.request(
        "GET",
        f"{settings.graph_base_url}/me/messages",
        token,
        params=query_params,
        headers=headers,
    )
    return {
        "items": [
            {
                "id": item.get("id"),
                "subject": item.get("subject"),
                "from": _map_recipient(item.get("from")),
                "received_datetime": item.get("receivedDateTime"),
                "is_read": item.get("isRead"),
                "has_attachments": item.get("hasAttachments"),
            }
            for item in payload.get("value", [])
        ],
        "next_cursor": _next_cursor(payload),
    }


async def create_draft(graph: GraphClient, token: str, params: dict) -> dict:
    payload = {
        "subject": params.get("subject"),
        "body": _map_body_out(params.get("body")),
        "toRecipients": [_map_recipient_out(r) for r in params.get("to", [])],
        "ccRecipients": [_map_recipient_out(r) for r in params.get("cc", [])],
        "bccRecipients": [_map_recipient_out(r) for r in params.get("bcc", [])],
    }
    response = await graph.request(
        "POST", f"{settings.graph_base_url}/me/messages", token, json=payload
    )
    return {"draft_id": response.get("id"), "message": response}


async def send_draft(graph: GraphClient, token: str, draft_id: str) -> dict:
    await graph.request(
        "POST", f"{settings.graph_base_url}/me/messages/{draft_id}/send", token
    )
    return {"status": "sent", "sent_message_id": draft_id}


async def reply(
    graph: GraphClient, token: str, message_id: str, reply_all: bool, comment: dict
) -> dict:
    endpoint = "replyAll" if reply_all else "reply"
    payload = {"comment": comment.get("content", "")}
    await graph.request(
        "POST",
        f"{settings.graph_base_url}/me/messages/{message_id}/{endpoint}",
        token,
        json=payload,
    )
    return {"status": "sent", "sent_message_id": message_id}


async def mark_read(
    graph: GraphClient, token: str, message_id: str, is_read: bool
) -> dict:
    await graph.request(
        "PATCH",
        f"{settings.graph_base_url}/me/messages/{message_id}",
        token,
        json={"isRead": is_read},
    )
    return {"status": "ok"}


async def move_message(
    graph: GraphClient, token: str, message_id: str, destination_folder_id: str
) -> dict:
    payload = {"destinationId": destination_folder_id}
    response = await graph.request(
        "POST",
        f"{settings.graph_base_url}/me/messages/{message_id}/move",
        token,
        json=payload,
    )
    return {
        "status": "ok",
        "message_id": response.get("id"),
        "destination_folder_id": destination_folder_id,
    }


async def get_attachment(
    graph: GraphClient,
    token: str,
    message_id: str,
    attachment_id: str,
    include_content_base64: bool,
) -> dict:
    payload = await graph.request(
        "GET",
        f"{settings.graph_base_url}/me/messages/{message_id}/attachments/{attachment_id}",
        token,
    )
    attachment = _map_attachment(payload)
    if include_content_base64:
        attachment["content_base64"] = payload.get("contentBytes")
    return {"attachment": attachment}


def _map_recipient(entry: dict | None) -> dict | None:
    if not entry:
        return None
    email = entry.get("emailAddress", {})
    return {"email": email.get("address"), "name": email.get("name")}


def _map_recipient_out(entry: dict) -> dict:
    return {"emailAddress": {"address": entry.get("email"), "name": entry.get("name")}}


def _map_body(body: dict | None) -> dict | None:
    if not body:
        return None
    return {
        "content_type": body.get("contentType", "html").lower(),
        "content": body.get("content"),
    }


def _map_body_out(body: dict | None) -> dict:
    if not body:
        return {"contentType": "HTML", "content": ""}
    content_type = body.get("content_type", "html").upper()
    return {"contentType": content_type, "content": body.get("content", "")}


def _map_attachment(attachment: dict) -> dict:
    return {
        "attachment_id": attachment.get("id"),
        "name": attachment.get("name"),
        "content_type": attachment.get("contentType"),
        "size_bytes": attachment.get("size"),
    }
