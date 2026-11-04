"""Shared helpers for the Miro tool modules.

Pagination: Miro's v2 list endpoints already return an opaque `cursor`
field for the next page — this service passes it straight through in both
directions, no re-encoding needed (unlike chargebee-mcp's PRD-17977
situation, which needed a codec to paper over a compound non-opaque
cursor). See docs/tickets/PRD-21312.md "Data & API contract".
"""

from typing import Any

from .._json import MAX_CHARS, dump_json_capped, error_envelope, fit_count, fits

NO_CREDS = error_envelope(
    "not_configured",
    "No Miro credentials configured. Send the X-Miro-Access-Token header.",
    False,
)

DEFAULT_LIMIT = 50
MAX_LIMIT = 200

LIMIT_DESC = f"Max results per page (1-{MAX_LIMIT}, default {DEFAULT_LIMIT})."
CURSOR_DESC = (
    "Pagination cursor from a previous response's cursor field. Omit for the "
    "first page; pass the exact value you received to get the next page."
)


def clamp_limit(limit: int) -> int:
    """Enforce the service's own hard cap regardless of what the caller asked for."""
    if limit < 1:
        return 1
    return min(limit, MAX_LIMIT)


def list_envelope(
    list_key: str, items: list[dict], cursor: str | None, max_chars: int = MAX_CHARS
) -> str:
    """Build the standard list-tool response: {<list_key>: [...], cursor, has_more},
    capped at the service's size limit (AC15) if the raw items would exceed it.

    `cursor` here is Miro's own next-page cursor (already opaque — passed
    through as-is); `has_more` is derived from whether Miro returned one,
    OR from local truncation if the page itself had to be cut down further
    to fit the character cap.
    """
    data: dict[str, Any] = {list_key: items, "cursor": cursor, "has_more": cursor is not None}
    if not fits(data, max_chars):
        count = fit_count(data, list_key, max_chars)
        data[list_key] = items[:count]
        data["has_more"] = True
    return dump_json_capped(data, max_chars)
