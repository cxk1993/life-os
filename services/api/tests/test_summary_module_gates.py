"""summary 模块判据测试（U2 端点层 · S-1/S-2/S-3/R-1）。

★ 本文件是 workbuddy 对知默 summary 模块的「判据测试支援」——
  按 astrbot《安全审查 · U2 端点层三条必加判据》逐条断言（总监令 57 全采纳）。

判据对照：
- S-1 转发目标由内核注册表决定（防 SSRF）→ 断言 _SUMMARY_TARGETS 为固定常量
- S-2 token 透传 + 超时 → 当前**转发未带 Authorization**（欠实现），以 xfail 钉住，候修转绿
- R-1 内核只许转发不许解释 → data 必须原样透传，不得添加/解析业务字段
（S-3 审计形状候模块补审计后补测）

设计：MockTransport 注入（不依赖真实四家端点）；asyncio.run 包裹（零 pytest-asyncio 依赖）。
"""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from modules.summary.router import _SUMMARY_TARGETS, _fetch_plugin_summary


def _run(coro):
    return asyncio.run(coro)


# ── S-1 · 转发目标由内核注册表决定 ─────────────────────────────────────
def test_s1_targets_are_fixed_registry() -> None:
    """注册表为固定四家常量：目标不由请求参数决定（防 SSRF 的根本）。"""
    assert _SUMMARY_TARGETS == ["calendar", "todo", "diary", "review"]


# ── R-1 · 内核只许转发，不许解释 ───────────────────────────────────────
def test_r1_data_passthrough_untouched() -> None:
    """200 时 data **原样透传**：不解析、不裁剪、不添加任何业务字段。"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"anyBusiness": {"nested": [1, 2]}, "weird": None})

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="http://test"
        ) as client:
            return await _fetch_plugin_summary("todo", client)

    r = _run(run())
    assert r["status"] == "ok"
    assert r["data"] == {"anyBusiness": {"nested": [1, 2]}, "weird": None}


def test_r1_404_is_not_found_not_error() -> None:
    """404 = 未实现（合法三态之一），status 必须是 not_found 而非 error。"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "Not Found"})

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="http://test"
        ) as client:
            return await _fetch_plugin_summary("todo", client)

    r = _run(run())
    assert r["status"] == "not_found"


def test_r1_5xx_is_error_and_module_never_crashes() -> None:
    """5xx → error 状态（缺一不塌：单家失败只影响自己）。"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="http://test"
        ) as client:
            return await _fetch_plugin_summary("todo", client)

    r = _run(run())
    assert r["status"] == "error"


def test_r1_network_failure_is_error_not_crash() -> None:
    """网络异常（连接拒绝等）→ error 状态，模块不崩（缺一不塌）。"""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="http://test"
        ) as client:
            return await _fetch_plugin_summary("todo", client)

    r = _run(run())
    assert r["status"] == "error"


# ── S-2 · token 透传 + 超时（★ 当前欠实现，xfail 钉住候修）──────────────
@pytest.mark.xfail(
    reason="S-2a 候修：转发应透传调用者 Authorization（当前 _fetch_plugin_summary 不收 headers，"
    "today-summary 若要求鉴权会 401 —— 静默失败同族）",
    strict=False,
)
def test_s2a_forwards_caller_authorization() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={})

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="http://test"
        ) as client:
            # 调用者带 token —— 期望转发时**原样透传**给插件端点
            client.headers["Authorization"] = "Bearer caller-token-123"
            return await _fetch_plugin_summary("todo", client)

    _run(run())
    assert captured.get("auth") == "Bearer caller-token-123", (
        "S-2a：转发必须透传调用者 Authorization（否则 today-summary 端点若有鉴权会 401，"
        "聚合卡把'没权限'误显示成'没数据'—— 静默失败）"
    )
    # 传出去的必须是**调用者的 token**（不能用内部 token 冒充 —— S-2 的"不绕权限"）
    assert "Bearer caller-token-123" in json.dumps(captured)
