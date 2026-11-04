"""Board item tools: read any item type, create sticky notes/cards, update,
and delete a single explicit item.

Tool naming convention: miro_<action>_<resource>
"""

from collections.abc import Callable
from typing import Annotated, Literal

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from .._json import dump_json_capped, error_envelope
from ..api_client import MiroClient, MiroError
from ._common import CURSOR_DESC, LIMIT_DESC, NO_CREDS, clamp_limit, list_envelope

# Item types whose content this service can update directly via their own
# type-specific endpoint. Every other type (shape, text, image, frame,
# document, embed, app_card, ...) only supports a position/parent update
# through Miro's generic /items/{id} endpoint — passing `content` for one
# of those returns invalid_argument rather than silently dropping it.
_CONTENT_UPDATABLE_TYPES = {"sticky_note", "card"}

ItemType = Literal[
    "card",
    "sticky_note",
    "shape",
    "text",
    "image",
    "frame",
    "document",
    "embed",
    "app_card",
]


def register(mcp: FastMCP, client_factory: Callable[[], MiroClient | None]) -> None:
    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def miro_list_board_items(
        board_id: Annotated[str, Field(description="The board's unique ID.")],
        item_type: Annotated[
            ItemType | None, Field(description="Restrict results to this item type.")
        ] = None,
        limit: Annotated[int, Field(description=LIMIT_DESC)] = 50,
        cursor: Annotated[str | None, Field(description=CURSOR_DESC)] = None,
    ) -> str:
        """List the items placed on a board, optionally filtered by type."""
        client = client_factory()
        if client is None:
            return NO_CREDS
        try:
            result = await client.get(
                f"/boards/{board_id}/items",
                params={"type": item_type, "limit": clamp_limit(limit), "cursor": cursor},
            )
        except MiroError as e:
            return e.to_envelope()
        items = result.get("data") or []
        next_cursor = result.get("cursor")
        return list_envelope("items", items, next_cursor)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def miro_get_item(
        board_id: Annotated[str, Field(description="The board's unique ID.")],
        item_id: Annotated[str, Field(description="The item's unique ID.")],
    ) -> str:
        """Get a single item's full details by ID."""
        client = client_factory()
        if client is None:
            return NO_CREDS
        try:
            result = await client.get(f"/boards/{board_id}/items/{item_id}")
            return dump_json_capped(result)
        except MiroError as e:
            return e.to_envelope()

    @mcp.tool()
    async def miro_create_sticky_note(
        board_id: Annotated[str, Field(description="The board's unique ID.")],
        content: Annotated[str, Field(description="Text content of the sticky note.")],
        shape: Annotated[
            str | None, Field(description='Sticky-note shape, e.g. "square" or "rectangle".')
        ] = None,
        fill_color: Annotated[
            str | None, Field(description='Background color name, e.g. "yellow", "light_blue".')
        ] = None,
        x: Annotated[float | None, Field(description="X position on the board canvas.")] = None,
        y: Annotated[float | None, Field(description="Y position on the board canvas.")] = None,
    ) -> str:
        """Create a sticky-note item on a board. Not idempotent — each call
        creates a new sticky note.
        """
        client = client_factory()
        if client is None:
            return NO_CREDS
        body = {
            "data": {"content": content, "shape": shape},
            "style": {"fillColor": fill_color} if fill_color else None,
            "position": {"x": x, "y": y} if x is not None or y is not None else None,
        }
        try:
            result = await client.post(f"/boards/{board_id}/sticky_notes", body)
            return dump_json_capped(result)
        except MiroError as e:
            return e.to_envelope()

    @mcp.tool()
    async def miro_create_card(
        board_id: Annotated[str, Field(description="The board's unique ID.")],
        title: Annotated[str, Field(description="Card title.")],
        description: Annotated[
            str | None, Field(description="Optional card body text.")
        ] = None,
        x: Annotated[float | None, Field(description="X position on the board canvas.")] = None,
        y: Annotated[float | None, Field(description="Y position on the board canvas.")] = None,
    ) -> str:
        """Create a card item on a board. Not idempotent — each call creates
        a new card.
        """
        client = client_factory()
        if client is None:
            return NO_CREDS
        body = {
            "data": {"title": title, "description": description},
            "position": {"x": x, "y": y} if x is not None or y is not None else None,
        }
        try:
            result = await client.post(f"/boards/{board_id}/cards", body)
            return dump_json_capped(result)
        except MiroError as e:
            return e.to_envelope()

    @mcp.tool(annotations=ToolAnnotations(idempotentHint=True))
    async def miro_update_item(
        board_id: Annotated[str, Field(description="The board's unique ID.")],
        item_id: Annotated[str, Field(description="The item's unique ID.")],
        item_type: Annotated[
            ItemType,
            Field(
                description=(
                    "The item's actual type. Content updates are only supported for "
                    "sticky_note and card; every other type accepts a position-only update."
                )
            ),
        ],
        content: Annotated[
            str | None,
            Field(
                description=(
                    "New text content (sticky_note) or title (card). Invalid for any "
                    "other item_type."
                )
            ),
        ] = None,
        x: Annotated[float | None, Field(description="New X position.")] = None,
        y: Annotated[float | None, Field(description="New Y position.")] = None,
    ) -> str:
        """Update an existing item's content and/or position."""
        client = client_factory()
        if client is None:
            return NO_CREDS

        position = {"x": x, "y": y} if x is not None or y is not None else None

        if content is not None and item_type not in _CONTENT_UPDATABLE_TYPES:
            return error_envelope(
                "invalid_argument",
                f"content updates are not supported for item_type={item_type!r}; "
                f"only {sorted(_CONTENT_UPDATABLE_TYPES)} support content updates",
                False,
            )

        if item_type == "sticky_note":
            path = f"/boards/{board_id}/sticky_notes/{item_id}"
            data = {"content": content} if content is not None else None
            body = {"data": data, "position": position}
        elif item_type == "card":
            path = f"/boards/{board_id}/cards/{item_id}"
            data = {"title": content} if content is not None else None
            body = {"data": data, "position": position}
        else:
            path = f"/boards/{board_id}/items/{item_id}"
            body = {"position": position}

        try:
            result = await client.patch(path, body)
            return dump_json_capped(result)
        except MiroError as e:
            return e.to_envelope()

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
    async def miro_delete_item(
        board_id: Annotated[str, Field(description="The board's unique ID.")],
        item_id: Annotated[
            str, Field(description="The single explicit item ID to delete. No bulk form exists.")
        ],
    ) -> str:
        """Permanently delete exactly one item from a board. Irreversible —
        there is no undo and no bulk/fuzzy form; an unknown item_id returns
        not_found, never a silent success.
        """
        client = client_factory()
        if client is None:
            return NO_CREDS
        try:
            await client.delete(f"/boards/{board_id}/items/{item_id}")
            return dump_json_capped({"deleted": True, "item_id": item_id})
        except MiroError as e:
            return e.to_envelope()
