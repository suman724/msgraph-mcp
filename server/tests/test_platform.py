import pytest

from msgraph_mcp.tools import platform


class FakeGraph:
    async def request(self, method, url, token, params=None, **_kwargs):
        assert method == "GET"
        assert url.endswith("/me")
        assert params["$select"] == "id,displayName,userPrincipalName,mail"
        return {
            "id": "user-1",
            "displayName": "Test User",
            "userPrincipalName": "user@example.com",
            "mail": "user@example.com",
        }


@pytest.mark.asyncio
async def test_get_profile():
    graph = FakeGraph()
    result = await platform.get_profile(graph, "token")

    assert result["profile"]["id"] == "user-1"
    assert result["profile"]["display_name"] == "Test User"
