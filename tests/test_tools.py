"""tools/list snapshot + error-envelope mapping tests.

No network calls: tool enumeration goes through FastMCP's in-process
list_tools(), and the error-code mapping is tested directly against
MiroError, independent of any real HTTP request.
"""

import json

import pytest

from miro_mcp.api_client import MiroError
from miro_mcp.config import Settings
from miro_mcp.server import create_mcp_server

EXPECTED_REQUIRED = {
    "miro_list_boards": set(),
    "miro_get_board": {"board_id"},
    "miro_create_board": {"name"},
    "miro_list_board_items": {"board_id"},
    "miro_get_item": {"board_id", "item_id"},
    "miro_create_sticky_note": {"board_id", "content"},
    "miro_create_card": {"board_id", "title"},
    "miro_update_item": {"board_id", "item_id", "item_type"},
    "miro_delete_item": {"board_id", "item_id"},
    "miro_list_board_members": {"board_id"},
}

READ_ONLY_TOOLS = {
    "miro_list_boards",
    "miro_get_board",
    "miro_list_board_items",
    "miro_get_item",
    "miro_list_board_members",
}
IDEMPOTENT_TOOLS = {"miro_update_item"}
DESTRUCTIVE_TOOLS = {"miro_delete_item"}
# create_board/create_sticky_note/create_card are intentionally left without
# an annotation: they're neither read-only, idempotent, nor destructive.
NO_ANNOTATION_TOOLS = {"miro_create_board", "miro_create_sticky_note", "miro_create_card"}


@pytest.mark.asyncio
async def test_tools_list_snapshot():
    mcp = create_mcp_server(Settings())
    tools = await mcp.list_tools()
    names = {t.name for t in tools}
    assert names == set(EXPECTED_REQUIRED), f"unexpected tool set: {names}"
    assert len(names) == 10

    by_name = {t.name: t for t in tools}
    for name, expected_required in EXPECTED_REQUIRED.items():
        tool = by_name[name]
        required = set(tool.inputSchema.get("required", []))
        assert required == expected_required, f"{name}: required={required}"

        assert len(tool.description or "") <= 500, f"{name}: description too long"
        first_line = (tool.description or "").strip().splitlines()[0]
        assert len(first_line) <= 100, f"{name}: first line too long: {first_line!r}"

        annotations = tool.annotations
        if name in READ_ONLY_TOOLS:
            assert annotations is not None and annotations.readOnlyHint is True, name
        elif name in IDEMPOTENT_TOOLS:
            assert annotations is not None and annotations.idempotentHint is True, name
        elif name in DESTRUCTIVE_TOOLS:
            assert annotations is not None and annotations.destructiveHint is True, name
        elif name in NO_ANNOTATION_TOOLS:
            assert annotations is None or (
                not annotations.readOnlyHint
                and not annotations.destructiveHint
                and not annotations.idempotentHint
            ), name


def test_delete_item_tool_is_annotated_destructive():
    import asyncio

    mcp = create_mcp_server(Settings())
    tools = asyncio.run(mcp.list_tools())
    by_name = {t.name: t for t in tools}
    assert by_name["miro_delete_item"].annotations.destructiveHint is True


@pytest.mark.asyncio
async def test_service_instructions_present_and_bounded():
    mcp = create_mcp_server(Settings())
    assert mcp.instructions
    assert len(mcp.instructions) <= 1500


@pytest.mark.parametrize(
    "status_code,expected_code,expected_retryable",
    [
        (0, "upstream_error", True),
        (400, "invalid_argument", False),
        (401, "unauthorized", False),
        (403, "unauthorized", False),
        (404, "not_found", False),
        (422, "invalid_argument", False),
        (429, "rate_limited", True),
        (500, "upstream_error", True),
        (503, "upstream_error", True),
    ],
)
def test_error_envelope_mapping(status_code, expected_code, expected_retryable):
    err = MiroError(status_code, "boom")
    envelope = json.loads(err.to_envelope())
    assert envelope["error"]["code"] == expected_code
    assert envelope["error"]["retryable"] is expected_retryable
    assert envelope["error"]["message"] == "boom"
