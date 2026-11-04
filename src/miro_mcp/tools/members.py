"""Board member (collaborator) tools.

Tool naming convention: miro_<action>_<resource>
"""

from collections.abc import Callable
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from ..api_client import MiroClient, MiroError
from ._common import CURSOR_DESC, LIMIT_DESC, NO_CREDS, clamp_limit, list_envelope


def register(mcp: FastMCP, client_factory: Callable[[], MiroClient | None]) -> None:
    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def miro_list_board_members(
        board_id: Annotated[str, Field(description="The board's unique ID.")],
        limit: Annotated[int, Field(description=LIMIT_DESC)] = 50,
        cursor: Annotated[str | None, Field(description=CURSOR_DESC)] = None,
    ) -> str:
        """List the collaborators who have access to a board (id, name, role)."""
        client = client_factory()
        if client is None:
            return NO_CREDS
        try:
            result = await client.get(
                f"/boards/{board_id}/members",
                params={"limit": clamp_limit(limit), "cursor": cursor},
            )
        except MiroError as e:
            return e.to_envelope()
        items = result.get("data") or []
        next_cursor = result.get("cursor")
        return list_envelope("members", items, next_cursor)
