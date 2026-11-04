"""Upstream error mapping: 429 -> rate_limited, 5xx -> upstream_error, both
retryable. Verifies the retry/backoff path eventually surfaces the right
envelope rather than hanging or raising an unstructured exception."""

import json

import httpx
import pytest
import respx

from miro_mcp import api_client as api_client_module
from miro_mcp.api_client import MiroClient, MiroError

BASE = "https://api.miro.com/v2"


@pytest.fixture(autouse=True)
def _reset_shared_client(monkeypatch):
    api_client_module._http_client = None
    # Keep the retry loop in this test file fast and deterministic.
    monkeypatch.setattr(api_client_module.asyncio, "sleep", _fast_sleep)
    yield
    api_client_module._http_client = None


async def _fast_sleep(_seconds):
    return None


@pytest.mark.asyncio
@respx.mock
async def test_miro_429_maps_to_rate_limited_retryable():
    respx.get(f"{BASE}/boards").mock(
        return_value=httpx.Response(
            429, json={"message": "Too many requests"}, headers={"Retry-After": "0"}
        )
    )
    client = MiroClient("tok", base_url=BASE)
    with pytest.raises(MiroError) as exc_info:
        await client.get("/boards")
    envelope = json.loads(exc_info.value.to_envelope())
    assert envelope["error"]["code"] == "rate_limited"
    assert envelope["error"]["retryable"] is True


@pytest.mark.asyncio
@respx.mock
async def test_miro_5xx_maps_to_upstream_error_retryable():
    respx.get(f"{BASE}/boards").mock(
        return_value=httpx.Response(503, json={"message": "Service unavailable"})
    )
    client = MiroClient("tok", base_url=BASE)
    with pytest.raises(MiroError) as exc_info:
        await client.get("/boards")
    envelope = json.loads(exc_info.value.to_envelope())
    assert envelope["error"]["code"] == "upstream_error"
    assert envelope["error"]["retryable"] is True
