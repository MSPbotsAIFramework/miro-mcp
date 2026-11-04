"""Board-item tool tests, driven through FastMCP.call_tool against a
FakeClient (see conftest.py) — no real network calls."""

import pytest
from conftest import call_tool, mcp_with

from miro_mcp.api_client import MiroError
from miro_mcp.tools import items


@pytest.mark.asyncio
async def test_list_board_items_bounded_and_paginated(fake_client):
    page = [{"id": f"i{i}", "type": "sticky_note"} for i in range(5)]
    fake_client.queue_get({"data": page, "cursor": "cur-2"})
    mcp = mcp_with(items.register, fake_client)

    out = await call_tool(mcp, "miro_list_board_items", board_id="b1")

    assert out["items"] == page
    assert out["cursor"] == "cur-2"
    assert out["has_more"] is True
    path, params = fake_client.get_calls[0]
    assert path == "/boards/b1/items"
    assert params["limit"] == 50


@pytest.mark.asyncio
async def test_list_board_items_filters_by_type(fake_client):
    fake_client.queue_get({"data": [], "cursor": None})
    mcp = mcp_with(items.register, fake_client)

    await call_tool(mcp, "miro_list_board_items", board_id="b1", item_type="card")

    _path, params = fake_client.get_calls[0]
    assert params["type"] == "card"


@pytest.mark.asyncio
async def test_get_item_returns_details(fake_client):
    fake_client.queue_get({"id": "i1", "type": "card", "data": {"title": "Ship it"}})
    mcp = mcp_with(items.register, fake_client)

    out = await call_tool(mcp, "miro_get_item", board_id="b1", item_id="i1")

    assert out["id"] == "i1"
    assert out["data"]["title"] == "Ship it"
    assert fake_client.get_calls[0][0] == "/boards/b1/items/i1"


@pytest.mark.asyncio
async def test_get_item_unknown_id_returns_not_found_error(fake_client):
    fake_client.queue_get(MiroError(404, "Item not found"))
    mcp = mcp_with(items.register, fake_client)

    out = await call_tool(mcp, "miro_get_item", board_id="b1", item_id="missing")

    assert out["error"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_create_sticky_note_posts_content_and_returns_id(fake_client):
    fake_client.queue_post({"id": "sn1", "data": {"content": "Hello"}})
    mcp = mcp_with(items.register, fake_client)

    out = await call_tool(mcp, "miro_create_sticky_note", board_id="b1", content="Hello")

    path, body = fake_client.post_calls[0]
    assert path == "/boards/b1/sticky_notes"
    assert body["data"]["content"] == "Hello"
    assert out["id"] == "sn1"


@pytest.mark.asyncio
async def test_create_card_posts_title_and_returns_id(fake_client):
    fake_client.queue_post({"id": "card1", "data": {"title": "Launch"}})
    mcp = mcp_with(items.register, fake_client)

    out = await call_tool(mcp, "miro_create_card", board_id="b1", title="Launch")

    path, body = fake_client.post_calls[0]
    assert path == "/boards/b1/cards"
    assert body["data"]["title"] == "Launch"
    assert out["id"] == "card1"


@pytest.mark.asyncio
async def test_update_item_patches_content(fake_client):
    fake_client.queue_patch({"id": "sn1", "data": {"content": "Updated"}})
    mcp = mcp_with(items.register, fake_client)

    out = await call_tool(
        mcp,
        "miro_update_item",
        board_id="b1",
        item_id="sn1",
        item_type="sticky_note",
        content="Updated",
    )

    path, body = fake_client.patch_calls[0]
    assert path == "/boards/b1/sticky_notes/sn1"
    assert body["data"]["content"] == "Updated"
    assert out["data"]["content"] == "Updated"


@pytest.mark.asyncio
async def test_update_item_invalid_field_for_type_returns_invalid_argument(fake_client):
    mcp = mcp_with(items.register, fake_client)

    out = await call_tool(
        mcp,
        "miro_update_item",
        board_id="b1",
        item_id="sh1",
        item_type="shape",
        content="not allowed",
    )

    assert out["error"]["code"] == "invalid_argument"
    assert out["error"]["retryable"] is False
    # No HTTP call was made — the check short-circuits before touching the client.
    assert fake_client.patch_calls == []


@pytest.mark.asyncio
async def test_delete_item_removes_single_explicit_id(fake_client):
    fake_client.queue_delete(None)
    mcp = mcp_with(items.register, fake_client)

    out = await call_tool(mcp, "miro_delete_item", board_id="b1", item_id="i1")

    assert out["deleted"] is True
    assert out["item_id"] == "i1"
    assert fake_client.delete_calls == ["/boards/b1/items/i1"]


@pytest.mark.asyncio
async def test_delete_item_unknown_id_returns_not_found_not_silent_success(fake_client):
    fake_client.queue_delete(MiroError(404, "Item not found"))
    mcp = mcp_with(items.register, fake_client)

    out = await call_tool(mcp, "miro_delete_item", board_id="b1", item_id="missing")

    assert out["error"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_large_item_list_is_capped_with_has_more_not_silently_dropped(fake_client):
    page = [
        {"id": f"i{i}", "type": "sticky_note", "data": {"content": "x" * 200}}
        for i in range(500)
    ]
    fake_client.queue_get({"data": page, "cursor": None})
    mcp = mcp_with(items.register, fake_client)

    out = await call_tool(mcp, "miro_list_board_items", board_id="b1")

    assert len(out["items"]) < len(page)
    assert out["has_more"] is True
