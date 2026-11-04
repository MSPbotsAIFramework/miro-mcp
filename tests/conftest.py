"""Shared test fixtures: a FakeClient standing in for MiroClient so tool
tests drive the real registered tool functions (via FastMCP.call_tool)
without any real network calls.
"""

import json

import pytest
from mcp.server.fastmcp import FastMCP


class FakeClient:
    """Stands in for MiroClient: each verb pops a queued canned response (or
    raises a queued exception) and records every call for assertions."""

    def __init__(self):
        self.get_calls: list[tuple[str, dict]] = []
        self.post_calls: list[tuple[str, dict]] = []
        self.patch_calls: list[tuple[str, dict]] = []
        self.delete_calls: list[str] = []
        self._get_queue: list = []
        self._post_queue: list = []
        self._patch_queue: list = []
        self._delete_queue: list = []

    def queue_get(self, *results):
        self._get_queue.extend(results)

    def queue_post(self, *results):
        self._post_queue.extend(results)

    def queue_patch(self, *results):
        self._patch_queue.extend(results)

    def queue_delete(self, *results):
        self._delete_queue.extend(results)

    async def get(self, path, params=None):
        self.get_calls.append((path, dict(params or {})))
        return _pop_or_raise(self._get_queue)

    async def post(self, path, body=None):
        self.post_calls.append((path, dict(body or {})))
        return _pop_or_raise(self._post_queue)

    async def patch(self, path, body=None):
        self.patch_calls.append((path, dict(body or {})))
        return _pop_or_raise(self._patch_queue)

    async def delete(self, path):
        self.delete_calls.append(path)
        return _pop_or_raise(self._delete_queue) if self._delete_queue else None


def _pop_or_raise(queue):
    value = queue.pop(0)
    if isinstance(value, Exception):
        raise value
    return value


@pytest.fixture
def fake_client():
    return FakeClient()


def mcp_with(register_fn, fake_client):
    mcp = FastMCP(name="test")
    register_fn(mcp, lambda: fake_client)
    return mcp


async def call_tool(mcp, tool_name, **args):
    _content, structured = await mcp.call_tool(tool_name, args)
    return json.loads(structured["result"])
