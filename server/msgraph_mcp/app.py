import hashlib
import json

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .auth import OIDCValidator
from .cache import RedisCache
from .config import settings
from .errors import MCPError, as_error_payload
from .graph import GraphClient
from .logging import configure_logging
from .services import AuthService, TokenService
from .session import SessionResolver
from .telemetry import configure_telemetry, instrument_fastapi
from .token_store import TokenStore
from .tools import calendar, drive, mail

try:
    from mcp.server import Server
    from mcp.server.fastapi import create_app as create_mcp_app
except ImportError as exc:  # pragma: no cover - runtime guard
    raise RuntimeError(
        "MCP SDK not installed. Install the official MCP Python SDK."
    ) from exc


configure_logging()
configure_telemetry(
    "msgraph-mcp", settings.otel_exporter_otlp_endpoint, settings.datadog_api_key
)

cache = RedisCache()
token_store = TokenStore()
graph = GraphClient()
auth_service = AuthService(cache, token_store, graph)
token_service = TokenService(cache, token_store)
oidc_validator = OIDCValidator()
session_resolver = SessionResolver(cache, token_store, oidc_validator)

server = Server("msgraph-mcp")


def _idempotency_cache_key(session: dict, tool_name: str, key: str) -> str:
    return f"{session['tenant_id']}:{session['user_id']}:{tool_name}:{key}"


async def _resolve_session(
    mcp_session_id: str | None, authorization: str | None
) -> dict:
    bearer = ""
    if authorization and authorization.lower().startswith("bearer "):
        bearer = authorization.split(" ", 1)[1]
    return await session_resolver.resolve(mcp_session_id or "", bearer)


async def _idempotent(
    session: dict, tool_name: str, idempotency_key: str | None, handler
):
    if not idempotency_key:
        return await handler()

    cache_key = _idempotency_cache_key(session, tool_name, idempotency_key)
    cached = cache.get_idempotency(cache_key)
    if cached and "result" in cached:
        return cached["result"]

    stored = token_store.check_idempotency(
        session["tenant_id"], session["user_id"], idempotency_key
    )
    if stored and stored.get("result"):
        return json.loads(stored["result"])

    result = await handler()
    result_hash = hashlib.sha256(
        json.dumps(result, sort_keys=True).encode("utf-8")
    ).hexdigest()
    cache.cache_idempotency(cache_key, {"result": result, "hash": result_hash})
    token_store.put_idempotency(
        session["tenant_id"],
        session["user_id"],
        idempotency_key,
        tool_name,
        result,
        result_hash,
    )
    return result


@server.tool("auth_begin_pkce")
async def auth_begin_pkce(
    scopes: list[str], redirect_uri: str | None = None, login_hint: str | None = None
) -> dict:
    result = auth_service.begin_pkce(scopes, redirect_uri, login_hint)
    return {
        "authorization_url": result.authorization_url,
        "state": result.state,
        "code_challenge_method": "S256",
    }


@server.tool("auth_complete_pkce")
async def auth_complete_pkce(
    code: str, state: str, redirect_uri: str | None = None
) -> dict:
    return await auth_service.complete_pkce(code, state, redirect_uri)


@server.tool("auth_get_status")
async def auth_get_status(
    mcp_session_id: str, authorization: str | None = None
) -> dict:
    session = await _resolve_session(mcp_session_id, authorization)
    return {
        "authenticated": True,
        "granted_scopes": session.get("scopes", []),
        "expires_at": session.get("expires_at"),
    }


@server.tool("auth_logout")
async def auth_logout(mcp_session_id: str, authorization: str | None = None) -> dict:
    await _resolve_session(mcp_session_id, authorization)
    return {"status": "logged_out"}


@server.tool("system_health")
async def system_health() -> dict:
    return {"status": "ok"}


@server.tool("system_whoami")
async def system_whoami(authorization: str | None = None) -> dict:
    bearer = ""
    if authorization and authorization.lower().startswith("bearer "):
        bearer = authorization.split(" ", 1)[1]
    claims = await oidc_validator.validate(bearer)
    return {"claims": claims}


@server.tool("mail_list_folders")
async def mail_list_folders(
    mcp_session_id: str,
    authorization: str | None = None,
    include_hidden: bool = False,
    pagination: dict | None = None,
) -> dict:
    session = await _resolve_session(mcp_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await mail.list_folders(graph, token, include_hidden, pagination)


@server.tool("mail_list_messages")
async def mail_list_messages(
    mcp_session_id: str, authorization: str | None = None, **params
) -> dict:
    session = await _resolve_session(mcp_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await mail.list_messages(graph, token, params)


@server.tool("mail_get_message")
async def mail_get_message(
    mcp_session_id: str,
    message_id: str,
    authorization: str | None = None,
    include_body: bool = True,
    include_attachments: bool = False,
) -> dict:
    session = await _resolve_session(mcp_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await mail.get_message(
        graph, token, message_id, include_body, include_attachments
    )


@server.tool("mail_search_messages")
async def mail_search_messages(
    mcp_session_id: str, authorization: str | None = None, **params
) -> dict:
    session = await _resolve_session(mcp_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await mail.search_messages(graph, token, params)


@server.tool("mail_create_draft")
async def mail_create_draft(
    mcp_session_id: str, authorization: str | None = None, **params
) -> dict:
    session = await _resolve_session(mcp_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await _idempotent(
        session,
        "mail_create_draft",
        params.get("idempotency_key"),
        lambda: mail.create_draft(graph, token, params),
    )


@server.tool("mail_send_draft")
async def mail_send_draft(
    mcp_session_id: str,
    draft_id: str,
    authorization: str | None = None,
    idempotency_key: str | None = None,
) -> dict:
    session = await _resolve_session(mcp_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await _idempotent(
        session,
        "mail_send_draft",
        idempotency_key,
        lambda: mail.send_draft(graph, token, draft_id),
    )


@server.tool("mail_reply")
async def mail_reply(
    mcp_session_id: str,
    message_id: str,
    comment: dict,
    authorization: str | None = None,
    reply_all: bool = False,
    idempotency_key: str | None = None,
) -> dict:
    session = await _resolve_session(mcp_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await _idempotent(
        session,
        "mail_reply",
        idempotency_key,
        lambda: mail.reply(graph, token, message_id, reply_all, comment),
    )


@server.tool("mail_mark_read")
async def mail_mark_read(
    mcp_session_id: str,
    message_id: str,
    is_read: bool,
    authorization: str | None = None,
) -> dict:
    session = await _resolve_session(mcp_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await mail.mark_read(graph, token, message_id, is_read)


@server.tool("mail_move_message")
async def mail_move_message(
    mcp_session_id: str,
    message_id: str,
    destination_folder_id: str,
    authorization: str | None = None,
) -> dict:
    session = await _resolve_session(mcp_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await mail.move_message(graph, token, message_id, destination_folder_id)


@server.tool("mail_get_attachment")
async def mail_get_attachment(
    mcp_session_id: str,
    message_id: str,
    attachment_id: str,
    authorization: str | None = None,
    include_content_base64: bool = False,
) -> dict:
    session = await _resolve_session(mcp_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await mail.get_attachment(
        graph, token, message_id, attachment_id, include_content_base64
    )


@server.tool("calendar_list_calendars")
async def calendar_list_calendars(
    mcp_session_id: str,
    authorization: str | None = None,
    pagination: dict | None = None,
) -> dict:
    session = await _resolve_session(mcp_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await calendar.list_calendars(graph, token, pagination)


@server.tool("calendar_list_events")
async def calendar_list_events(
    mcp_session_id: str, authorization: str | None = None, **params
) -> dict:
    session = await _resolve_session(mcp_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await calendar.list_events(graph, token, params)


@server.tool("calendar_get_event")
async def calendar_get_event(
    mcp_session_id: str, event_id: str, authorization: str | None = None
) -> dict:
    session = await _resolve_session(mcp_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await calendar.get_event(graph, token, event_id)


@server.tool("calendar_create_event")
async def calendar_create_event(
    mcp_session_id: str, authorization: str | None = None, **params
) -> dict:
    session = await _resolve_session(mcp_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await _idempotent(
        session,
        "calendar_create_event",
        params.get("transaction_id"),
        lambda: calendar.create_event(graph, token, params),
    )


@server.tool("calendar_update_event")
async def calendar_update_event(
    mcp_session_id: str,
    event_id: str,
    patch: dict,
    authorization: str | None = None,
    idempotency_key: str | None = None,
) -> dict:
    session = await _resolve_session(mcp_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await _idempotent(
        session,
        "calendar_update_event",
        idempotency_key,
        lambda: calendar.update_event(graph, token, event_id, patch),
    )


@server.tool("calendar_delete_event")
async def calendar_delete_event(
    mcp_session_id: str, event_id: str, authorization: str | None = None
) -> dict:
    session = await _resolve_session(mcp_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await calendar.delete_event(graph, token, event_id)


@server.tool("calendar_respond_to_invite")
async def calendar_respond_to_invite(
    mcp_session_id: str, authorization: str | None = None, **params
) -> dict:
    session = await _resolve_session(mcp_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await _idempotent(
        session,
        "calendar_respond_to_invite",
        params.get("idempotency_key"),
        lambda: calendar.respond_to_invite(graph, token, params),
    )


@server.tool("calendar_find_availability")
async def calendar_find_availability(
    mcp_session_id: str, authorization: str | None = None, **params
) -> dict:
    session = await _resolve_session(mcp_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await calendar.find_availability(graph, token, params)


@server.tool("drive_get_default")
async def drive_get_default(
    mcp_session_id: str, authorization: str | None = None
) -> dict:
    session = await _resolve_session(mcp_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await drive.get_default_drive(graph, token)


@server.tool("drive_list_children")
async def drive_list_children(
    mcp_session_id: str, authorization: str | None = None, **params
) -> dict:
    session = await _resolve_session(mcp_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await drive.list_children(graph, token, params)


@server.tool("drive_get_item")
async def drive_get_item(
    mcp_session_id: str, authorization: str | None = None, **params
) -> dict:
    session = await _resolve_session(mcp_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await drive.get_item(graph, token, params)


@server.tool("drive_search")
async def drive_search(
    mcp_session_id: str, authorization: str | None = None, **params
) -> dict:
    session = await _resolve_session(mcp_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await drive.search(graph, token, params)


@server.tool("drive_download_file")
async def drive_download_file(
    mcp_session_id: str, authorization: str | None = None, **params
) -> dict:
    session = await _resolve_session(mcp_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await drive.download_file(graph, token, params)


@server.tool("drive_upload_small_file")
async def drive_upload_small_file(
    mcp_session_id: str, authorization: str | None = None, **params
) -> dict:
    session = await _resolve_session(mcp_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await _idempotent(
        session,
        "drive_upload_small_file",
        params.get("idempotency_key"),
        lambda: drive.upload_small_file(graph, token, params),
    )


@server.tool("drive_create_upload_session")
async def drive_create_upload_session(
    mcp_session_id: str, authorization: str | None = None, **params
) -> dict:
    session = await _resolve_session(mcp_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await _idempotent(
        session,
        "drive_create_upload_session",
        params.get("idempotency_key"),
        lambda: drive.create_upload_session(graph, token, params),
    )


@server.tool("drive_upload_chunk")
async def drive_upload_chunk(
    mcp_session_id: str, authorization: str | None = None, **params
) -> dict:
    session = await _resolve_session(mcp_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await drive.upload_chunk(graph, token, params)


@server.tool("drive_create_folder")
async def drive_create_folder(
    mcp_session_id: str, authorization: str | None = None, **params
) -> dict:
    session = await _resolve_session(mcp_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await drive.create_folder(graph, token, params)


@server.tool("drive_delete_item")
async def drive_delete_item(
    mcp_session_id: str, authorization: str | None = None, **params
) -> dict:
    session = await _resolve_session(mcp_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await drive.delete_item(graph, token, params)


@server.tool("drive_share_create_link")
async def drive_share_create_link(
    mcp_session_id: str, authorization: str | None = None, **params
) -> dict:
    session = await _resolve_session(mcp_session_id, authorization)
    token = await token_service.get_access_token(session)
    return await drive.create_share_link(graph, token, params)


app = FastAPI()


@app.exception_handler(MCPError)
async def handle_mcp_error(_, exc: MCPError):
    return JSONResponse(status_code=exc.status, content=as_error_payload(exc))


app.mount("/mcp", create_mcp_app(server))
instrument_fastapi(app)
