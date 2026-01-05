# MCP Tool Catalog

This catalog defines the MCP tools exposed by the server. Full JSON schemas live under `design/schemas/`.

---

## Conventions

- Inputs are JSON objects.
- Pagination: `{ page_size, cursor }`.
- Responses return `{ items, next_cursor }` for list operations.
- Side-effect tools accept `idempotency_key` where applicable.
- Base64 file payloads are limited to 100 MB; prefer `download_url` for larger files.

---

## Auth tools

| Tool | Description | Scopes | Side effects |
| --- | --- | --- | --- |
| `auth_begin_pkce` | Start OAuth2 PKCE flow and return auth URL | n/a | No |
| `auth_complete_pkce` | Exchange auth code for tokens and create session | n/a | Yes (token storage) |
| `auth_get_status` | Check auth/session status | n/a | No |
| `auth_logout` | Delete stored tokens for session | n/a | Yes (token removal) |

---

## Mail tools (Outlook)

Schema file: `design/schemas/email.tools.json`

| Tool | Description | Scopes | Side effects |
| --- | --- | --- | --- |
| `mail_list_folders` | List mail folders | `Mail.Read` | No |
| `mail_list_messages` | List messages by folder and time | `Mail.Read` | No |
| `mail_get_message` | Get message details | `Mail.Read` | No |
| `mail_search_messages` | Search messages by query | `Mail.Read` | No |
| `mail_create_draft` | Create draft email | `Mail.ReadWrite` | Yes |
| `mail_send_draft` | Send an existing draft | `Mail.Send` | Yes |
| `mail_reply` | Reply or reply-all to a message | `Mail.Send` | Yes |
| `mail_mark_read` | Mark message read/unread | `Mail.ReadWrite` | Yes |
| `mail_move_message` | Move a message to another folder | `Mail.ReadWrite` | Yes |
| `mail_get_attachment` | Get attachment metadata or content | `Mail.Read` | No |

---

## Calendar tools

Schema file: `design/schemas/calendar.tools.json`

| Tool | Description | Scopes | Side effects |
| --- | --- | --- | --- |
| `calendar_list_calendars` | List calendars | `Calendars.Read` | No |
| `calendar_list_events` | List events in a time range | `Calendars.Read` | No |
| `calendar_get_event` | Get event details | `Calendars.Read` | No |
| `calendar_create_event` | Create a calendar event | `Calendars.ReadWrite` | Yes |
| `calendar_update_event` | Update an event | `Calendars.ReadWrite` | Yes |
| `calendar_delete_event` | Delete an event | `Calendars.ReadWrite` | Yes |
| `calendar_respond_to_invite` | Respond to an invite | `Calendars.ReadWrite` | Yes |
| `calendar_find_availability` | Find free/busy slots | `Calendars.Read` | No |

---

## OneDrive tools

Schema file: `design/schemas/onedrive.tools.json`

| Tool | Description | Scopes | Side effects |
| --- | --- | --- | --- |
| `drive_get_default` | Get the default drive | `Files.Read` | No |
| `drive_list_children` | List children of a folder | `Files.Read` | No |
| `drive_get_item` | Get item metadata | `Files.Read` | No |
| `drive_search` | Search items | `Files.Read` | No |
| `drive_download_file` | Download file (or link) | `Files.Read` | No |
| `drive_upload_small_file` | Upload small file | `Files.ReadWrite` | Yes |
| `drive_create_upload_session` | Create a large-file upload session | `Files.ReadWrite` | Yes |
| `drive_upload_chunk` | Upload a chunk to a session | `Files.ReadWrite` | Yes |
| `drive_create_folder` | Create a folder | `Files.ReadWrite` | Yes |
| `drive_delete_item` | Delete an item | `Files.ReadWrite` | Yes |
| `drive_share_create_link` | Create sharing link | `Files.ReadWrite` | Yes |

**Large file uploads**
- Use `drive_create_upload_session` and `drive_upload_chunk`.
- Chunks should be aligned to 320 KiB boundaries; cap base64 chunk payloads at 100 MB.

---

## Platform tools

Schema file: `design/schemas/system.tools.json`

| Tool | Description |
| --- | --- |
| `system_health` | Health check for the MCP server |
| `system_whoami` | Return authenticated caller info |
| `system_get_profile` | Return Graph `/me` profile (id, displayName, UPN, mail) |
