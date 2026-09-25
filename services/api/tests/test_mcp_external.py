"""TX-MCP-EXT · 通用外部 MCP 源桥（网络全 mock · 零业务词）。"""
from __future__ import annotations

import json

import httpx
import pytest

from modules.mcp import external as ext


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXTERNAL_MCP_URL", "https://ext.example/mcp")
    monkeypatch.setenv("EXTERNAL_MCP_TOKEN", "tok_test")
    monkeypatch.setenv("EXTERNAL_MCP_PREFIX", "ext")
    monkeypatch.setenv("EXTERNAL_MCP_TOOLS", "list_things,get_thing,search")
    monkeypatch.setenv("EXTERNAL_MCP_WRITE_TOOLS", "create_thing")
    monkeypatch.setenv("EXTERNAL_MCP_ALLOW_WRITE", "0")


def test_read_tools_only_by_default() -> None:
    tools = ext.external_tools()
    assert len(tools) == 3
    assert all(not t.is_write for t in tools)
    assert tools[0].name.startswith("ext_")
    assert all(t.scope == "ext:read" for t in tools)


def test_write_tools_gated() -> None:
    import os

    os.environ["EXTERNAL_MCP_ALLOW_WRITE"] = "1"
    try:
        names = {t.name for t in ext.external_tools()}
        assert "ext_create_thing" in names
    finally:
        os.environ["EXTERNAL_MCP_ALLOW_WRITE"] = "0"


def test_unconfigured_is_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXTERNAL_MCP_TOKEN", "")
    assert ext.external_tools() == []


def test_call_external_forwards(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("authorization", "")
        captured["rpc"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "result": {"content": [{"type": "text", "text": "ok"}], "isError": False},
            },
        )

    transport = httpx.MockTransport(handler)
    real = httpx.Client

    def fake_client(*a, **kw):  # noqa: ANN002, ANN003
        kw["transport"] = transport
        return real(*a, **kw)

    monkeypatch.setattr(ext.httpx, "Client", fake_client)
    tool = ext.find_external("ext_list_things")
    assert tool is not None
    ok, body = ext.call_external(tool, {"limit": 3})
    assert ok is True
    assert captured["auth"].startswith("Bearer ")
    assert captured["rpc"]["method"] == "tools/call"
    assert captured["rpc"]["params"]["name"] == "list_things"
    assert body is not None


def test_write_blocked_when_disallowed() -> None:
    tool = ext.ExternalTool(
        name="ext_create_thing",
        upstream="create_thing",
        description="x",
        scope="ext:write",
        is_write=True,
    )
    ok, body = ext.call_external(tool, {})
    assert ok is False
    assert "disabled" in str(body)
