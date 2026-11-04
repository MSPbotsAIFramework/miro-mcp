import contextvars
import sys

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from .api_client import MiroClient
from .config import Settings

# ─────────────────────────────────────────────────────────────────────────────
# Per-request access-token contextvar for gateway mode.
# GatewayTokenMiddleware sets this before the MCP handler runs.
# Python asyncio copies context per task, so concurrent requests are isolated.
# ─────────────────────────────────────────────────────────────────────────────
_gateway_creds_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "miro_gateway_creds", default=None
)


def get_client_from_context(settings: Settings) -> MiroClient | None:
    """Resolve the active MiroClient for the current request context."""
    if settings.auth_mode == "gateway":
        token = _gateway_creds_var.get()
    else:
        token = settings.miro_access_token

    if not token:
        return None
    return MiroClient(token, base_url=settings.miro_base_url)


class GatewayTokenMiddleware:
    """ASGI middleware for gateway mode.

    Reads the configured access-token header from each request and stores
    it in the contextvar for the duration of that request. Returns 401 if
    the header is missing on /mcp requests.
    """

    def __init__(self, app: ASGIApp, settings: Settings):
        self.app = app
        self.settings = settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if not path.startswith("/mcp"):
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        # Header lookup is case-insensitive in Starlette
        token = request.headers.get(self.settings.miro_access_token_header.lower())
        if not token:
            response = JSONResponse(
                {
                    "error": "Missing credentials",
                    "message": (
                        f"Requires the {self.settings.miro_access_token_header} header"
                    ),
                    "required_headers": [self.settings.miro_access_token_header],
                },
                status_code=401,
            )
            await response(scope, receive, send)
            return

        ctx_token = _gateway_creds_var.set(token)
        try:
            await self.app(scope, receive, send)
        finally:
            _gateway_creds_var.reset(ctx_token)


def create_mcp_server(settings: Settings) -> FastMCP:
    """Build the FastMCP server instance and register all tools."""
    # DNS-rebinding protection is disabled because the container runs behind
    # mcp-gateway on an internal Docker network and is never publicly exposed.
    mcp = FastMCP(
        name="miro-mcp",
        instructions=(
            "Miro is a visual whiteboard and collaboration platform. This server "
            "manages boards and the items placed on them (sticky notes, cards, and "
            "other item types), plus board collaborators. Use it for: finding a "
            "board (miro_list_boards, optionally with a search query) or creating "
            "a new one (miro_create_board); reading a board's contents "
            "(miro_list_board_items, optionally filtered by item type, then "
            "miro_get_item for one item's full detail); adding content as an agent "
            "(miro_create_sticky_note for a quick note, miro_create_card for a "
            "titled card with a description); changing existing content "
            "(miro_update_item); removing a single item (miro_delete_item — "
            "destructive, takes exactly one explicit item_id, no bulk form); and "
            "listing who has access to a board (miro_list_board_members). Typical "
            "flow: miro_list_boards to find the target board, then "
            "miro_list_board_items to see what's on it, then create/update/delete "
            "tools to make the requested change. 5 of 10 tools are read-only "
            "queries; miro_delete_item is destructive."
        ),
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
        stateless_http=True,
        json_response=True,
    )

    def client_factory() -> MiroClient | None:
        return get_client_from_context(settings)

    if not settings.has_credentials:
        # Graceful degradation: register only a diagnostic tool when no credentials are available.
        @mcp.tool()
        async def miro_test_connection() -> str:
            """Test Miro API connection. Shows configuration requirements when
            credentials are missing."""
            return (
                "Error: Missing Miro credentials.\n\n"
                "Set the required environment variable:\n"
                "  MIRO_ACCESS_TOKEN=your_access_token\n\n"
                "Or use gateway mode (per-request credentials):\n"
                "  AUTH_MODE=gateway\n"
                f"  Send header: {settings.miro_access_token_header}: your_access_token"
            )

        print(
            "Warning: No Miro credentials found. Only the diagnostic tool is available.",
            file=sys.stderr,
        )
        return mcp

    # Register all tool modules here.
    from .tools import boards, items, members

    boards.register(mcp, client_factory)
    items.register(mcp, client_factory)
    members.register(mcp, client_factory)

    return mcp
