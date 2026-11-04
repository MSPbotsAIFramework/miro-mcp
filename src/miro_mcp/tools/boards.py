"""Board tools: discover and create Miro boards.

Tool naming convention: miro_<action>_<resource>
"""

from collections.abc import Callable
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from .._json import dump_json_capped
from ..api_client import MiroClient, MiroError
from ._common import CURSOR_DESC, LIMIT_DESC, NO_CREDS, clamp_limit, list_envelope


def register(mcp: FastMCP, client_factory: Callable[[], MiroClient | None]) -> None:
    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def miro_list_boards(
        limit: Annotated[int, Field(description=LIMIT_DESC)] = 50,
        query: Annotated[
            str | None, Field(description="Free-text search over board name/description.")
        ] = None,
        team_id: Annotated[
            str | None, Field(description="Restrict results to boards owned by this team.")
        ] = None,
        cursor: Annotated[str | None, Field(description=CURSOR_DESC)] = None,
    ) -> str:
        """List boards visible to this token. Returns an empty list (not an
        error) if the account has no boards.
        """
        client = client_factory()
        if client is None:
            return NO_CREDS
        try:
            result = await client.get(
                "/boards",
                params={
                    "limit": clamp_limit(limit),
                    "query": query,
                    "team_id": team_id,
                    "cursor": cursor,
                },
            )
        except MiroError as e:
            return e.to_envelope()
        items = result.get("data") or []
        next_cursor = result.get("cursor")
        return list_envelope("boards", items, next_cursor)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def miro_get_board(
        board_id: Annotated[str, Field(description="The board's unique ID.")],
    ) -> str:
        """Get a single board's details by ID."""
        client = client_factory()
        if client is None:
            return NO_CREDS
        try:
            result = await client.get(f"/boards/{board_id}")
            return dump_json_capped(result)
        except MiroError as e:
            return e.to_envelope()

    @mcp.tool()
    async def miro_create_board(
        name: Annotated[str, Field(description="Name for the new board.")],
        description: Annotated[
            str | None, Field(description="Optional description shown on the board.")
        ] = None,
    ) -> str:
        """Create a new, empty board. Not idempotent — each call creates a
        new board; calling it twice with the same name creates two boards.
        """
        client = client_factory()
        if client is None:
            return NO_CREDS
        body = {"name": name, "description": description}
        try:
            result = await client.post("/boards", body)
            return dump_json_capped(result)
        except MiroError as e:
            return e.to_envelope()
