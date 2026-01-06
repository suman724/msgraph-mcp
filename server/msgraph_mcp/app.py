import hashlib
import json
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .auth import OIDCValidator
from .cache import create_cache
from .config import settings
from .errors import MCPError, as_error_payload
from .graph import GraphClient
from .logging import configure_logging
from .services import AuthService, TokenService
from .session import SessionResolver
from .telemetry import configure_telemetry, instrument_fastapi
from .tools import calendar, drive, mail, platform

try:
    from mcp.server import FastMCP
except ImportError as exc:  # pragma: no cover - runtime guard
    raise RuntimeError(
        "MCP SDK not installed. Install the official MCP Python SDK."
    ) from exc


configure_logging()
if not settings.disable_otel:
    configure_telemetry(
        "msgraph-mcp", settings.otel_exporter_otlp_endpoint, settings.datadog_api_key
    )

cache = create_cache()
graph = GraphClient()
auth_service = AuthService(cache, graph)
token_service = TokenService(cache)
oidc_validator = OIDCValidator()
session_resolver = SessionResolver(cache, oidc_validator)

server = FastMCP(
    name="msgraph-mcp",
    streamable_http_path="/",
    json_response=True,
    stateless_http=True,
)
mcp_app = server.streamable_http_app()


def _idempotency_cache_key(session: dict, tool_name: str, key: str) -> str:
    return f"{session['tenant_id']}:{session['user_id']}:{tool_name}:{key}"


def _get_authorization_header(authorization: str | None) -> str | None:
    if authorization:
        return authorization
    try:
        request = server.get_context().request_context.request
    except LookupError:  # pragma: no cover - request context missing
        return None
    if not request:  # pragma: no cover - transport without request
        return None
    return request.headers.get("authorization")


def _extract_bearer(authorization: str | None) -> str:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1]
    return ""


async def _require_client_token(authorization: str | None) -> None:
    if settings.disable_oidc_validation:
        return
    auth_header = _get_authorization_header(authorization)
    bearer = _extract_bearer(auth_header)
    if not bearer:
        raise MCPError("AUTH_REQUIRED", "Missing client token", status=401)
    await oidc_validator.validate(bearer)


async def _resolve_session(
    graph_session_id: str | None, authorization: str | None
) -> dict[str, Any]:
    auth_header = _get_authorization_header(authorization)
    bearer = _extract_bearer(auth_header)
    return await session_resolver.resolve(graph_session_id or "", bearer)


async def _idempotent(
    session: dict, tool_name: str, idempotency_key: str | None, handler
):
    if not idempotency_key:
        return await handler()

    cache_key = _idempotency_cache_key(session, tool_name, idempotency_key)
    cached = cache.get_idempotency(cache_key)
    if cached and "result" in cached:
        return cached["result"]

    result = await handler()
    result_hash = hashlib.sha256(
        json.dumps(result, sort_keys=True).encode("utf-8")
    ).hexdigest()
    cache.cache_idempotency(cache_key, {"result": result, "hash": result_hash})
    return result


@server.tool("auth_begin_pkce")
async def auth_begin_pkce(
    scopes: list[str], redirect_uri: str | None = None, login_hint: str | None = None
) -> dict[str, Any]:
    await _require_client_token(None)
    result = auth_service.begin_pkce(scopes, redirect_uri, login_hint)
    return {
        "authorization_url": result.authorization_url,
        "state": result.state,
        "code_challenge_method": "S256",
    }


@server.tool("auth_complete_pkce")
async def auth_complete_pkce(
    code: str, state: str, redirect_uri: str | None = None
) -> dict[str, Any]:
    await _require_client_token(None)
    return await auth_service.complete_pkce(code, state, redirect_uri)


@server.tool("auth_get_status")
async def auth_get_status(
    graph_session_id: str, authorization: str | None = None
) -> dict[str, Any]:
    session = await _resolve_session(graph_session_id, authorization)
    return {
        "authenticated": True,
        "granted_scopes": session.get("scopes", []),
        "expires_at": session.get("expires_at"),
    }


@server.tool("auth_logout")
async def auth_logout(
    graph_session_id: str, authorization: str | None = None
) -> dict[str, Any]:
    await _resolve_session(graph_session_id, authorization)
    cache.delete_session(graph_session_id)
    cache.delete_refresh_token(graph_session_id)
    return {"status": "logged_out"}


@server.tool("system_health")
async def system_health() -> dict[str, Any]:
    return {"status": "ok"}


@server.tool("system_whoami")
async def system_whoami(authorization: str | None = None) -> dict[str, Any]:
    auth_header = _get_authorization_header(authorization)
    bearer = _extract_bearer(auth_header)
    if settings.disable_oidc_validation:
        return {"claims": {}, "validation": "disabled"}
    claims = await oidc_validator.validate(bearer)
    return {"claims": claims}


@server.tool("system_get_profile")
async def system_get_profile(
    graph_session_id: str, authorization: str | None = None
) -> dict[str, Any]:
    session = await _resolve_session(graph_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await platform.get_profile(graph, token)


@server.tool("mail_list_folders")
async def mail_list_folders(
    graph_session_id: str,
    authorization: str | None = None,
    include_hidden: bool = False,
    pagination: dict | None = None,
) -> dict[str, Any]:
    session = await _resolve_session(graph_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await mail.list_folders(graph, token, include_hidden, pagination)


@server.tool("mail_list_messages")
async def mail_list_messages(
    graph_session_id: str, authorization: str | None = None, **params
) -> dict[str, Any]:
    session = await _resolve_session(graph_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await mail.list_messages(graph, token, params)


@server.tool("mail_get_message")
async def mail_get_message(
    graph_session_id: str,
    message_id: str,
    authorization: str | None = None,
    include_body: bool = True,
    include_attachments: bool = False,
) -> dict[str, Any]:
    session = await _resolve_session(graph_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await mail.get_message(
        graph, token, message_id, include_body, include_attachments
    )


@server.tool("mail_search_messages")
async def mail_search_messages(
    graph_session_id: str, authorization: str | None = None, **params
) -> dict[str, Any]:
    session = await _resolve_session(graph_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await mail.search_messages(graph, token, params)


@server.tool("mail_create_draft")
async def mail_create_draft(
    graph_session_id: str, authorization: str | None = None, **params
) -> dict[str, Any]:
    session = await _resolve_session(graph_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await _idempotent(
        session,
        "mail_create_draft",
        params.get("idempotency_key"),
        lambda: mail.create_draft(graph, token, params),
    )


@server.tool("mail_send_draft")
async def mail_send_draft(
    graph_session_id: str,
    draft_id: str,
    authorization: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    session = await _resolve_session(graph_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await _idempotent(
        session,
        "mail_send_draft",
        idempotency_key,
        lambda: mail.send_draft(graph, token, draft_id),
    )


@server.tool("mail_reply")
async def mail_reply(
    graph_session_id: str,
    message_id: str,
    comment: dict,
    authorization: str | None = None,
    reply_all: bool = False,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    session = await _resolve_session(graph_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await _idempotent(
        session,
        "mail_reply",
        idempotency_key,
        lambda: mail.reply(graph, token, message_id, reply_all, comment),
    )


@server.tool("mail_mark_read")
async def mail_mark_read(
    graph_session_id: str,
    message_id: str,
    is_read: bool,
    authorization: str | None = None,
) -> dict[str, Any]:
    session = await _resolve_session(graph_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await mail.mark_read(graph, token, message_id, is_read)


@server.tool("mail_move_message")
async def mail_move_message(
    graph_session_id: str,
    message_id: str,
    destination_folder_id: str,
    authorization: str | None = None,
) -> dict[str, Any]:
    session = await _resolve_session(graph_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await mail.move_message(graph, token, message_id, destination_folder_id)


@server.tool("mail_get_attachment")
async def mail_get_attachment(
    graph_session_id: str,
    message_id: str,
    attachment_id: str,
    authorization: str | None = None,
    include_content_base64: bool = False,
) -> dict[str, Any]:
    session = await _resolve_session(graph_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await mail.get_attachment(
        graph, token, message_id, attachment_id, include_content_base64
    )


@server.tool("calendar_list_calendars")
async def calendar_list_calendars(
    graph_session_id: str,
    authorization: str | None = None,
    pagination: dict | None = None,
) -> dict[str, Any]:
    session = await _resolve_session(graph_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await calendar.list_calendars(graph, token, pagination)


@server.tool("calendar_list_events")
async def calendar_list_events(
    graph_session_id: str, authorization: str | None = None, **params
) -> dict[str, Any]:
    session = await _resolve_session(graph_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await calendar.list_events(graph, token, params)


@server.tool("calendar_get_event")
async def calendar_get_event(
    graph_session_id: str, event_id: str, authorization: str | None = None
) -> dict[str, Any]:
    session = await _resolve_session(graph_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await calendar.get_event(graph, token, event_id)


@server.tool("calendar_create_event")
async def calendar_create_event(
    graph_session_id: str, authorization: str | None = None, **params
) -> dict[str, Any]:
    session = await _resolve_session(graph_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await _idempotent(
        session,
        "calendar_create_event",
        params.get("transaction_id"),
        lambda: calendar.create_event(graph, token, params),
    )


@server.tool("calendar_update_event")
async def calendar_update_event(
    graph_session_id: str,
    event_id: str,
    patch: dict,
    authorization: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    session = await _resolve_session(graph_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await _idempotent(
        session,
        "calendar_update_event",
        idempotency_key,
        lambda: calendar.update_event(graph, token, event_id, patch),
    )


@server.tool("calendar_delete_event")
async def calendar_delete_event(
    graph_session_id: str, event_id: str, authorization: str | None = None
) -> dict[str, Any]:
    session = await _resolve_session(graph_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await calendar.delete_event(graph, token, event_id)


@server.tool("calendar_respond_to_invite")
async def calendar_respond_to_invite(
    graph_session_id: str, authorization: str | None = None, **params
) -> dict[str, Any]:
    session = await _resolve_session(graph_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await _idempotent(
        session,
        "calendar_respond_to_invite",
        params.get("idempotency_key"),
        lambda: calendar.respond_to_invite(graph, token, params),
    )


@server.tool("calendar_find_availability")
async def calendar_find_availability(
    graph_session_id: str, authorization: str | None = None, **params
) -> dict[str, Any]:
    session = await _resolve_session(graph_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await calendar.find_availability(graph, token, params)


@server.tool("drive_get_default")
async def drive_get_default(
    graph_session_id: str, authorization: str | None = None
) -> dict[str, Any]:
    session = await _resolve_session(graph_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await drive.get_default_drive(graph, token)


@server.tool("drive_list_children")
async def drive_list_children(
    graph_session_id: str, authorization: str | None = None, **params
) -> dict[str, Any]:
    session = await _resolve_session(graph_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await drive.list_children(graph, token, params)


@server.tool("drive_get_item")
async def drive_get_item(
    graph_session_id: str, authorization: str | None = None, **params
) -> dict[str, Any]:
    session = await _resolve_session(graph_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await drive.get_item(graph, token, params)


@server.tool("drive_search")
async def drive_search(
    graph_session_id: str, authorization: str | None = None, **params
) -> dict[str, Any]:
    session = await _resolve_session(graph_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await drive.search(graph, token, params)


@server.tool("drive_download_file")
async def drive_download_file(
    graph_session_id: str, authorization: str | None = None, **params
) -> dict[str, Any]:
    session = await _resolve_session(graph_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await drive.download_file(graph, token, params)


@server.tool("drive_upload_small_file")
async def drive_upload_small_file(
    graph_session_id: str, authorization: str | None = None, **params
) -> dict[str, Any]:
    session = await _resolve_session(graph_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await _idempotent(
        session,
        "drive_upload_small_file",
        params.get("idempotency_key"),
        lambda: drive.upload_small_file(graph, token, params),
    )


@server.tool("drive_create_upload_session")
async def drive_create_upload_session(
    graph_session_id: str, authorization: str | None = None, **params
) -> dict[str, Any]:
    session = await _resolve_session(graph_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await _idempotent(
        session,
        "drive_create_upload_session",
        params.get("idempotency_key"),
        lambda: drive.create_upload_session(graph, token, params),
    )


@server.tool("drive_upload_chunk")
async def drive_upload_chunk(
    graph_session_id: str, authorization: str | None = None, **params
) -> dict[str, Any]:
    session = await _resolve_session(graph_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await drive.upload_chunk(graph, token, params)


@server.tool("drive_create_folder")
async def drive_create_folder(
    graph_session_id: str, authorization: str | None = None, **params
) -> dict[str, Any]:
    session = await _resolve_session(graph_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await drive.create_folder(graph, token, params)


@server.tool("drive_delete_item")
async def drive_delete_item(
    graph_session_id: str, authorization: str | None = None, **params
) -> dict[str, Any]:
    session = await _resolve_session(graph_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await drive.delete_item(graph, token, params)


@server.tool("drive_share_create_link")
async def drive_share_create_link(
    graph_session_id: str, authorization: str | None = None, **params
) -> dict[str, Any]:
    session = await _resolve_session(graph_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await drive.create_share_link(graph, token, params)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    async with server.session_manager.run():
        yield


app = FastAPI(lifespan=lifespan)


@app.exception_handler(MCPError)
async def handle_mcp_error(_, exc: MCPError):
    return JSONResponse(status_code=exc.status, content=as_error_payload(exc))


app.mount("/mcp", mcp_app)
instrument_fastapi(app)
