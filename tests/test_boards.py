"""Board tool tests, driven through FastMCP.call_tool against a FakeClient
(see conftest.py) — exercises the real registered tool code and MCP's own
argument parsing, with no real network calls."""

import pytest
from conftest import call_tool, mcp_with

from miro_mcp.api_client import MiroError
from miro_mcp.tools import boards


@pytest.mark.asyncio
async def test_list_boards_returns_bounded_results_with_cursor(fake_client):
    page = [{"id": f"b{i}", "name": f"Board {i}"} for i in range(3)]
    fake_client.queue_get({"data": page, "cursor": "next-page-token"})
    mcp = mcp_with(boards.register, fake_client)

    out = await call_tool(mcp, "miro_list_boards")

    assert out["boards"] == page
    assert out["cursor"] == "next-page-token"
    assert out["has_more"] is True
    path, params = fake_client.get_calls[0]
    assert path == "/boards"
    assert params["limit"] == 50  # default, clamped


@pytest.mark.asyncio
async def test_list_boards_search_query_is_forwarded(fake_client):
    fake_client.queue_get({"data": [], "cursor": None})
    mcp = mcp_with(boards.register, fake_client)

    await call_tool(mcp, "miro_list_boards", query="roadmap")

    _path, params = fake_client.get_calls[0]
    assert params["query"] == "roadmap"


@pytest.mark.asyncio
async def test_list_boards_empty_result_returns_empty_array_not_error(fake_client):
    fake_client.queue_get({"data": [], "cursor": None})
    mcp = mcp_with(boards.register, fake_client)

    out = await call_tool(mcp, "miro_list_boards")

    assert out["boards"] == []
    assert "error" not in out


@pytest.mark.asyncio
async def test_get_board_returns_details(fake_client):
    fake_client.queue_get({"id": "b1", "name": "Board 1", "viewLink": "https://miro.com/b1"})
    mcp = mcp_with(boards.register, fake_client)

    out = await call_tool(mcp, "miro_get_board", board_id="b1")

    assert out["id"] == "b1"
    assert out["name"] == "Board 1"
    assert fake_client.get_calls[0][0] == "/boards/b1"


@pytest.mark.asyncio
async def test_get_board_unknown_id_returns_not_found_error(fake_client):
    fake_client.queue_get(MiroError(404, "Board not found"))
    mcp = mcp_with(boards.register, fake_client)

    out = await call_tool(mcp, "miro_get_board", board_id="missing")

    assert out["error"]["code"] == "not_found"
    assert out["error"]["retryable"] is False


@pytest.mark.asyncio
async def test_create_board_posts_name_and_returns_new_board(fake_client):
    fake_client.queue_post({"id": "new-board", "name": "Sprint Planning"})
    mcp = mcp_with(boards.register, fake_client)

    out = await call_tool(mcp, "miro_create_board", name="Sprint Planning")

    path, body = fake_client.post_calls[0]
    assert path == "/boards"
    assert body == {"name": "Sprint Planning", "description": None}
    assert out["id"] == "new-board"
