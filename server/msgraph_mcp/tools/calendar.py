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


async def list_calendars(
    graph: GraphClient, token: str, pagination: dict | None
) -> dict:
    payload = await graph.request(
        "GET",
        f"{settings.graph_base_url}/me/calendars",
        token,
        params=_pagination_params(pagination),
    )
    return {
        "items": [
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "owner": _map_owner(item.get("owner")),
            }
            for item in payload.get("value", [])
        ],
        "next_cursor": _next_cursor(payload),
    }


async def list_events(graph: GraphClient, token: str, params: dict) -> dict:
    pagination = _pagination_params(params.get("pagination"))
    calendar_id = params.get("calendar_id")
    if calendar_id:
        url = f"{settings.graph_base_url}/me/calendars/{calendar_id}/events"
    else:
        url = f"{settings.graph_base_url}/me/events"

    filters = [
        f"start/dateTime ge '{params['start_datetime']}'",
        f"end/dateTime le '{params['end_datetime']}'",
    ]
    if not params.get("include_cancelled"):
        filters.append("isCancelled eq false")
    pagination["$filter"] = " and ".join(filters)

    payload = await graph.request("GET", url, token, params=pagination)
    return {
        "items": [_map_event(item) for item in payload.get("value", [])],
        "next_cursor": _next_cursor(payload),
    }


async def get_event(graph: GraphClient, token: str, event_id: str) -> dict:
    payload = await graph.request(
        "GET", f"{settings.graph_base_url}/me/events/{event_id}", token
    )
    return {"event": _map_event(payload)}


async def create_event(graph: GraphClient, token: str, params: dict) -> dict:
    payload = {
        "subject": params.get("subject"),
        "body": _map_body_out(params.get("body")),
        "start": _map_datetime(params.get("start_datetime"), params.get("timezone")),
        "end": _map_datetime(params.get("end_datetime"), params.get("timezone")),
        "location": {"displayName": params.get("location")},
        "attendees": [_map_attendee(a) for a in params.get("attendees", [])],
        "isOnlineMeeting": params.get("is_online_meeting", False),
        "onlineMeetingProvider": params.get(
            "online_meeting_provider", "teamsForBusiness"
        ),
    }
    calendar_id = params.get("calendar_id")
    url = f"{settings.graph_base_url}/me/events"
    if calendar_id:
        url = f"{settings.graph_base_url}/me/calendars/{calendar_id}/events"
    response = await graph.request("POST", url, token, json=payload)
    return {"event_id": response.get("id"), "event": _map_event(response)}


async def update_event(
    graph: GraphClient, token: str, event_id: str, patch: dict
) -> dict:
    await graph.request(
        "PATCH", f"{settings.graph_base_url}/me/events/{event_id}", token, json=patch
    )
    return {"status": "ok"}


async def delete_event(graph: GraphClient, token: str, event_id: str) -> dict:
    await graph.request(
        "DELETE", f"{settings.graph_base_url}/me/events/{event_id}", token
    )
    return {"status": "ok"}


async def respond_to_invite(graph: GraphClient, token: str, params: dict) -> dict:
    response = params.get("response")
    if response not in {"accept", "tentative", "decline"}:
        raise MCPError("VALIDATION_ERROR", "Invalid response")
    endpoint = {
        "accept": "accept",
        "tentative": "tentativelyAccept",
        "decline": "decline",
    }[response]
    payload = {
        "comment": params.get("comment", ""),
        "sendResponse": params.get("send_response", True),
    }
    await graph.request(
        "POST",
        f"{settings.graph_base_url}/me/events/{params['event_id']}/{endpoint}",
        token,
        json=payload,
    )
    return {"status": "ok"}


async def find_availability(graph: GraphClient, token: str, params: dict) -> dict:
    payload = {
        "schedules": [a.get("email") for a in params.get("attendees", [])],
        "startTime": {"dateTime": params.get("start_datetime"), "timeZone": "UTC"},
        "endTime": {"dateTime": params.get("end_datetime"), "timeZone": "UTC"},
        "availabilityViewInterval": params.get("interval_minutes", 30),
    }
    response = await graph.request(
        "POST",
        f"{settings.graph_base_url}/me/calendar/getSchedule",
        token,
        json=payload,
    )
    slots = []
    for schedule in response.get("value", []):
        for item in schedule.get("scheduleItems", []):
            slots.append(
                {
                    "start_datetime": item.get("start", {}).get("dateTime"),
                    "end_datetime": item.get("end", {}).get("dateTime"),
                    "is_available": item.get("status") == "free",
                }
            )
    return {"slots": slots}


def _map_owner(owner: dict | None) -> dict | None:
    if not owner:
        return None
    email = owner.get("emailAddress", {})
    return {"email": email.get("address"), "name": email.get("name")}


def _map_body_out(body: dict | None) -> dict:
    if not body:
        return {"contentType": "HTML", "content": ""}
    content_type = body.get("content_type", "html").upper()
    return {"contentType": content_type, "content": body.get("content", "")}


def _map_datetime(value: str | None, timezone: str | None) -> dict:
    return {"dateTime": value, "timeZone": timezone or "UTC"}


def _map_attendee(entry: dict) -> dict:
    return {
        "emailAddress": {"address": entry.get("email"), "name": entry.get("name")},
        "type": "required",
    }


def _map_event(event: dict) -> dict:
    return {
        "id": event.get("id"),
        "subject": event.get("subject"),
        "body": {
            "content_type": event.get("body", {}).get("contentType", "html").lower(),
            "content": event.get("body", {}).get("content"),
        },
        "start_datetime": event.get("start", {}).get("dateTime"),
        "end_datetime": event.get("end", {}).get("dateTime"),
        "timezone": event.get("start", {}).get("timeZone"),
        "location": event.get("location", {}).get("displayName"),
        "attendees": [
            {
                "email": attendee.get("emailAddress", {}).get("address"),
                "name": attendee.get("emailAddress", {}).get("name"),
            }
            for attendee in event.get("attendees", [])
        ],
        "is_cancelled": event.get("isCancelled"),
    }
