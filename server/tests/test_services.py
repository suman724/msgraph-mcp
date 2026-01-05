import base64

import pytest

from msgraph_mcp.errors import MCPError
from msgraph_mcp.services import decode_base64_payload


def test_decode_base64_payload_ok():
    raw = b"hello"
    payload = base64.b64encode(raw).decode("ascii")
    assert decode_base64_payload(payload, max_bytes=10) == raw


def test_decode_base64_payload_too_large():
    raw = b"x" * 11
    payload = base64.b64encode(raw).decode("ascii")
    with pytest.raises(MCPError) as exc:
        decode_base64_payload(payload, max_bytes=10)
    assert exc.value.code == "VALIDATION_ERROR"
