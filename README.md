# miro-mcp

Miro MCP Service — a stateless HTTP MCP server wrapping the [Miro REST API v2](https://developers.miro.com/reference/rest-api-reference) for whiteboard/collaboration use cases (board discovery and creation, board-item read/write — sticky notes, cards, and other item types — and board membership lookups).

**Tech stack:** Python 3.12 + uv + FastMCP (Starlette/Uvicorn)

<div align="center">

## MSPbots Connector

**The MCP Gateway built for MSPs: visible, controlled, and your data stays where it belongs.**

[**Get started at connect.mspbots.ai →**](https://connect.mspbots.ai)

</div>

---

MSPbots Connector gives your AI clients one MCP URL to reach your entire MSP stack (RMM, PSA, documentation, security, finance), and gives you control over who can call which tool and a record of everything that was called.

**Hosted service: [connect.mspbots.ai](https://connect.mspbots.ai)** · Free to use.

### Why Connector

![MSPbots Connector](https://stgoss.mspbots.ai/files/mcp/mspbots-mcp.png)

| | |
|---|---|
| **Visible** | Every tool call is logged: who, which vendor, when. Usage dashboard, CSV export, SIEM streaming. |
| **Controlled** | Role-based, per-tool allowlist. Deny by default. |
| **Protected** | Credentials encrypted per record. AI clients never see your vendor passwords or tokens. |
| **MSP-native** | Built for the MSP stack only: RMM, PSA, documentation, security, finance. |

### Quick start

1. **Sign up** at [connect.mspbots.ai](https://connect.mspbots.ai).
2. **Connect your vendors.** Pick from 150+ connectors and authorize each one on the vendor's own page, or bring your own API keys. No extra vendor accounts needed.
3. **Set access.** Create roles and decide which tools each role may call. Nothing is allowed until you allow it.
4. **Add your MCP URL to your AI client.** Copy the URL from your Connector dashboard into Claude, ChatGPT, Cursor, VS Code, Gemini, Codex, or any MCP-capable client.
5. **Ask your AI to do real work**, and watch every call appear in the audit log.

### Features

**Unified gateway**
- One MCP URL for all your AI clients
- 150+ connectors across the MSP stack
- Custom MCP servers supported, free
- Authorization happens on each vendor's own page; the AI never sees passwords or tokens
- Bring your own credentials: use the vendor API keys you already have
- Multiple accounts per app; connect once, reuse across AI clients
- Tool search: finds the right action for the task
- One sign-in; vendor credentials are injected behind the scenes and OAuth tokens refresh automatically

**Visibility**
- Audit log for every tool call (who, which vendor, when)
- Usage dashboard: call volume, top vendors, error rate, per-user activity
- Export audit logs to CSV, or stream to Loki, Graylog, or LogScale (SIEM)
- Optional recording of tool arguments and result summaries (off by default, enabled per organization)

**Control**
- Per-role, per-tool allowlist, deny by default
- owner / admin / member roles
- SCIM provisioning with Entra ID, Okta, JumpCloud, and Google Workspace

**Security**
- Credentials encrypted one record at a time (AES-256-GCM, per-record key)
- AI clients authenticate with OAuth 2.1 + PKCE
- Vendor responses are scanned for prompt-injection patterns and returned as structured data. This is one layer of defense, not a guarantee against every attack.
- Static egress IP for customer firewall and API allowlisting

### Pricing

**Free.**

Links: [connect.mspbots.ai](https://connect.mspbots.ai) · [mspbots.ai](https://mspbots.ai)

---

## When would an agent use this

Miro is a visual whiteboard and collaboration platform. An agent should reach for this MCP for requests like:

- "Find my team's planning board" / "Create a new board for this project" → `miro_list_boards` (optionally with a search query) / `miro_create_board`
- "What's on this board?" → `miro_list_board_items` (optionally filtered by item type), then `miro_get_item` for one item's full detail
- "Add a sticky note / card with this content" → `miro_create_sticky_note` / `miro_create_card`
- "Update this sticky note's text" / "Move this card" → `miro_update_item`
- "Remove this item from the board" → `miro_delete_item` (destructive — exactly one explicit item per call)
- "Who has access to this board?" → `miro_list_board_members`

## Scope

Out of Miro's full REST API v2 surface (boards, 10+ board-item subtypes with per-type CRUD, tags, visual "connector" arrow items, webhooks, and Enterprise-tier organization/team/project management), this service wraps **10 core tools** covering boards, the two most agent-relevant item types (sticky notes, cards) with generic read/update/delete for every other item type, and board membership — see [PRD-21312: Decisions made by DEV01](docs/tickets/PRD-21312.md#risks--dependencies) for the full rationale.

Excluded from this version (not asked for in the originating ticket, not a redesign if needed later): Enterprise org/team/project resources, webhooks, Miro's visual "connector" item type, board tags, board templates/duplication.

| Category | Count | Resources |
|---|---|---|
| Board | 3 | list, get, create |
| Board item | 6 | list, get, create sticky note, create card, update, delete |
| Board member | 1 | list collaborators |

## Quick Start

```bash
# Install dependencies
cd miro-mcp
uv sync

# Run in stdio mode (for Claude Desktop)
export MIRO_ACCESS_TOKEN="your_access_token"
uv run miro-mcp
```

## Configuration

Copy `.env.example` to `.env` and fill in your values:

| Variable | Default | Description |
|----------|---------|--------------|
| `MIRO_ACCESS_TOKEN` | — | Miro access token (env mode only) |
| `AUTH_MODE` | `gateway` | `gateway` = access token per-request via header (SOP-compliant); `env` = shared credential from an env var (local dev only) |
| `MCP_TRANSPORT` | `stdio` | `stdio` (Claude Desktop) or `http` (gateway) |
| `MCP_HTTP_PORT` | `8080` | HTTP server port |

Get your access token: create a Miro app under your account's Developer Team at [developers.miro.com](https://developers.miro.com), then generate a token for it (OAuth2, or a long-lived "service account" token — see Miro's ["Hello, World" guide](https://developers.miro.com/docs/rest-api-build-your-first-hello-world-app)).

## HEADER Authentication Parameters

In Gateway mode, every request must carry the following HTTP header:

| Header | Type | Required | Default | Allowed values | Description | Example |
|---|---|---|---|---|---|---|
| `X-Miro-Access-Token` | string | Yes | None | None | A Miro OAuth2 access token or service-account access token, scoped to the boards the caller wants an agent to reach. Obtained from the Miro app the account's Developer Team created. | `eyJtaXJvLm9yaWdpbiI6Im9uZSJ9...` |

## Claude Desktop Setup

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "miro": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/miro-mcp", "miro-mcp"],
      "env": {
        "MIRO_ACCESS_TOKEN": "your_access_token"
      }
    }
  }
}
```

## Transport Modes

### stdio (Claude Desktop / CLI)
```bash
export MIRO_ACCESS_TOKEN="your_access_token"
uv run miro-mcp
```

### HTTP — single-tenant
```bash
export MIRO_ACCESS_TOKEN="your_access_token"
export MCP_TRANSPORT="http"
export AUTH_MODE="env"
uv run miro-mcp
```

### HTTP — gateway / multi-tenant
```bash
export MCP_TRANSPORT="http"
export AUTH_MODE="gateway"
uv run miro-mcp
# Each request must include: X-Miro-Access-Token header
```

## Available Tools (10)

### Board — 3

| Tool | Description | Parameters |
|---|---|---|
| `miro_list_boards` | List boards visible to this token | `limit`, `query`, `team_id`, `cursor` |
| `miro_get_board` | Get a single board's details by ID | `board_id` |
| `miro_create_board` | Create a new, empty board | `name`, `description` |

### Board item — 6

| Tool | Description | Parameters |
|---|---|---|
| `miro_list_board_items` | List the items on a board, optionally filtered by type | `board_id`, `item_type`, `limit`, `cursor` |
| `miro_get_item` | Get a single item's full details by ID | `board_id`, `item_id` |
| `miro_create_sticky_note` | Create a sticky-note item on a board | `board_id`, `content`, `shape`, `fill_color`, `x`, `y` |
| `miro_create_card` | Create a card item on a board | `board_id`, `title`, `description`, `x`, `y` |
| `miro_update_item` | Update an existing item's content and/or position | `board_id`, `item_id`, `item_type`, `content`, `x`, `y` |
| `miro_delete_item` | Permanently delete exactly one item (destructive, no bulk form) | `board_id`, `item_id` |

### Board member — 1

| Tool | Description | Parameters |
|---|---|---|
| `miro_list_board_members` | List a board's collaborators (id, name, role) | `board_id`, `limit`, `cursor` |

### Pagination

All `list` tools accept `limit` (default 50, hard cap 200 enforced by this service regardless of what is requested) and `cursor`. Miro's own list-endpoint cursor is already opaque and resource-scoped, so this service passes it straight through in both directions — no re-encoding. A response's `has_more`/`cursor` fields signal whether more results exist.

### Item-type update support

`miro_update_item` supports content updates only for `sticky_note` and `card` (Miro's generic items endpoint supports position-only updates for every other type: `shape`, `text`, `image`, `frame`, `document`, `embed`, `app_card`). Passing `content` for any other `item_type` returns a structured `invalid_argument` error rather than silently dropping the field.

## Known Gaps

- **Verified by unit tests against a mocked Miro transport**, not a live Miro account — this is a first version and no test vendor account was available at delivery time (not a blocker per SOP; see `docs/tickets/PRD-21312.ac.json` `TC-MIRO-014`). The one case needing a real account ships `untested`; it does not block the rest of the suite.
- Exact Miro REST API v2 request/response field names for a few endpoints (generic item PATCH, sticky-note/card create body shape) are asserted from Miro's documented, stable resource model but have not been cross-checked field-by-field against a live response. If a live test later surfaces a mismatch, it is a small fix local to `tools/items.py` / `api_client.py`, not a design change.
- Tags, the visual "connector" (arrow) item type, Enterprise org/team/project management, and webhooks are out of scope for this version (see Scope above).
- `miro_update_item` requires the caller to already know the item's `item_type` (Miro's item-type-specific endpoints need it to route the PATCH correctly); callers typically get this from a prior `miro_list_board_items` or `miro_get_item` call.

## API Reference

- [Miro REST API Introduction](https://developers.miro.com/miro-ea/docs/miro-rest-api-introduction.md)
- [Miro REST API Reference](https://developers.miro.com/reference/rest-api-reference)
- [Miro — Build your first Hello World app](https://developers.miro.com/docs/rest-api-build-your-first-hello-world-app) (auth/token setup)
