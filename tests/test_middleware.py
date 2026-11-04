"""Gateway credential middleware tests: missing-header 401, and header
values correctly reaching the per-request contextvar (no global-state
leakage across requests, including under real concurrency).
"""

import asyncio

from starlette.testclient import TestClient

from miro_mcp.__main__ import _build_http_app
from miro_mcp.config import Settings
from miro_mcp.server import (
    GatewayTokenMiddleware,
    _gateway_creds_var,
    create_mcp_server,
    get_client_from_context,
)


def _make_app():
    settings = Settings()
    mcp = create_mcp_server(settings)
    return _build_http_app(mcp, settings), settings


def test_health_is_local_and_does_not_require_credentials():
    app, _ = _make_app()
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


def test_missing_credential_header_returns_401():
    app, _ = _make_app()
    with TestClient(app) as client:
        resp = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            headers={"Accept": "application/json, text/event-stream"},
        )
        assert resp.status_code == 401
        body = resp.json()
        assert "X-Miro-Access-Token" in body["required_headers"]


def test_empty_credential_header_returns_401():
    app, _ = _make_app()
    with TestClient(app) as client:
        resp = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            headers={
                "Accept": "application/json, text/event-stream",
                "X-Miro-Access-Token": "",
            },
        )
        assert resp.status_code == 401


def test_header_present_reaches_request_context():
    # Directly exercises the middleware's contextvar plumbing without a full
    # MCP protocol round-trip: confirms the header value that arrives on the
    # request is exactly what get_client_from_context sees, and that it is
    # reset afterward (no leakage to the next request).
    settings = Settings()
    seen = {}

    async def fake_app(scope, receive, send):
        seen["token"] = _gateway_creds_var.get()
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    middleware = GatewayTokenMiddleware(fake_app, settings)

    async def run():
        scope = {
            "type": "http",
            "path": "/mcp",
            "headers": [(b"x-miro-access-token", b"test-token-123")],
        }

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            pass

        await middleware(scope, receive, send)

    asyncio.run(run())
    assert seen["token"] == "test-token-123"
    # After the request completes, the contextvar must be reset — a fresh
    # get() outside any request context sees no leftover credential.
    assert _gateway_creds_var.get() is None


def test_concurrent_requests_do_not_leak_credentials_across_contextvar():
    """AC14/TC-MIRO-024: two concurrent requests carrying two different
    tokens must never observe each other's credential."""
    settings = Settings()
    observed = {}

    async def fake_app(scope, receive, send):
        name = scope["_test_name"]
        # Yield control so the two requests actually interleave instead of
        # running start-to-finish sequentially.
        await asyncio.sleep(0.01)
        observed[name] = _gateway_creds_var.get()
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    middleware = GatewayTokenMiddleware(fake_app, settings)

    async def call(name: str, token: str):
        scope = {
            "type": "http",
            "path": "/mcp",
            "_test_name": name,
            "headers": [(b"x-miro-access-token", token.encode())],
        }

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            pass

        await middleware(scope, receive, send)

    async def run():
        await asyncio.gather(call("a", "token-a"), call("b", "token-b"))

    asyncio.run(run())
    assert observed["a"] == "token-a"
    assert observed["b"] == "token-b"


def test_client_factory_returns_none_without_context():
    settings = Settings()
    assert get_client_from_context(settings) is None
