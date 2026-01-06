import pytest

from msgraph_mcp.auth import exchange_code_for_token
from msgraph_mcp.errors import MCPError


class FakeResponse:
    def __init__(self, status_code: int, payload: dict, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        return self._payload


class FakeClient:
    def __init__(self, response: FakeResponse) -> None:
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, _exc_type, _exc, _tb):
        return False

    async def post(self, _url, data=None):
        return self._response


@pytest.mark.asyncio
async def test_exchange_code_for_token_includes_error_detail(monkeypatch):
    response = FakeResponse(
        400,
        {"error": "invalid_grant", "error_description": "bad code"},
        text="invalid",
    )

    def fake_client(*_args, **_kwargs):
        return FakeClient(response)

    monkeypatch.setattr("msgraph_mcp.auth.httpx.AsyncClient", fake_client)

    with pytest.raises(MCPError) as exc:
        await exchange_code_for_token("code", "verifier", "http://cb", ["User.Read"])

    assert "bad code" in exc.value.message
