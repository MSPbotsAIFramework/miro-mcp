"""Board member tool tests, driven through FastMCP.call_tool against a
FakeClient (see conftest.py) — no real network calls."""

import pytest
from conftest import call_tool, mcp_with

from miro_mcp.tools import members


@pytest.mark.asyncio
async def test_list_board_members_bounded_and_paginated(fake_client):
    page = [
        {"id": "u1", "name": "Alice", "role": "owner"},
        {"id": "u2", "name": "Bob", "role": "editor"},
    ]
    fake_client.queue_get({"data": page, "cursor": None})
    mcp = mcp_with(members.register, fake_client)

    out = await call_tool(mcp, "miro_list_board_members", board_id="b1")

    assert out["members"] == page
    assert out["has_more"] is False
    path, params = fake_client.get_calls[0]
    assert path == "/boards/b1/members"
    assert params["limit"] == 50
