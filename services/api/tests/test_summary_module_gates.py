"""U2 聚合端点判据测试（★ 内核 BFF 侧 · S-1/S-2/S-3/R-1）。

★ 事故恢复（2026-09-24 15:1x，hermes 值班巡检）：
  workbuddy `cd05d60` 的判据测试锚在 modules/summary/router.py 的
  `_fetch_plugin_summary`（模块侧旧实现）。summary 模块收敛为薄壳后该函数已删除
  （且 15:22 进一步发现模块 /today 与内核 BFF /summary/today 路径遮蔽，
  模块端点永不触发——转发逻辑是死代码，router 已收敛为纯 /health 壳）。
  若 checkout 回 workbuddy 原测试必 ImportError——它测的对象已不存在。

★ 判据本身不能丢 → 锚点移到真正的实现：内核 BFF（core/app.py）：
  - `_fetch_one()`             模块级函数，转发单家 today-summary（可用 MockTransport 单测）
  - `_SUMMARY_PROVIDERS`       固定四元组（防 SSRF：目标不由请求参数决定）
  - `summary_today()`          鉴权 + token 透传 + 单家超时 + 审计不落 token（源码级断言）

判据对照（astrbot 安全审查 · 令 57 全采纳）：
  S-1  转发目标由内核注册表决定（防 SSRF）
  S-2  token 只透传给插件端点、不进 URL 不落日志 + 单家超时
  S-3  审计只记操作与状态，不含 Authorization
  R-1  内核只许转发不许解释：data 原样透传，不解析/裁剪/添加业务字段
"""
from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest

from core.app import _fetch_one


# ── 单家转发语义（R-1 透传 + 三态）──────────────────────────────────────
async def _call_fetch(
    handler: Any,
    pid: str = "todo",
    url: str = "http://t/api/v1/todo/today-summary",
    headers: dict[str, str] | None = None,
    timeout: float = 3.0,
) -> dict[str, Any]:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://t"
    ) as client:
        return await _fetch_one(client, pid, url, headers or {}, timeout)


def test_r1_200_data_passthrough_untouched() -> None:
    """200 → status ok + data **原样透传**（不含业务字段解析）。"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"anyBusiness": {"nested": [1, 2]}, "weird": None}
        )

    r = asyncio.run(_call_fetch(handler))
    assert r == {
        "id": "todo",
        "status": "ok",
        "data": {"anyBusiness": {"nested": [1, 2]}, "weird": None},
    }


def test_r1_404_is_not_implemented_not_error() -> None:
    """404 → not-implemented（合法三态之一，UI 显示「未实现」而非「出错」）。"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "Not Found"})

    r = asyncio.run(_call_fetch(handler))
    assert r == {"id": "todo", "status": "not-implemented"}


def test_r1_5xx_is_unavailable_module_never_crashes() -> None:
    """5xx → unavailable（缺一不塌，单家失败只影响自己）。"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    r = asyncio.run(_call_fetch(handler))
    assert r == {"id": "todo", "status": "unavailable"}


def test_r1_network_failure_is_unavailable_not_crash() -> None:
    """网络异常 → unavailable，模块不崩。"""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    r = asyncio.run(_call_fetch(handler))
    assert r == {"id": "todo", "status": "unavailable"}


# ── S-1 · 转发目标固定，不由请求参数决定（防 SSRF）────────────────────────
def test_s1_providers_are_fixed_registry() -> None:
    """_SUMMARY_PROVIDERS 为固定四源常量，请求参数无法控制转发目标。"""
    from core.app import create_app

    import inspect

    src = inspect.getsource(create_app)
    # 固定四元组内联在 create_app 内（BFF 端点定义处）
    day_seg = src.split('("/api/v1/', 1)[1]
    assert "/api/v1/calendar/today-summary" in src
    assert "/api/v1/todo/today-summary" in src
    assert "/api/v1/diary/today-summary" in src
    assert "/api/v1/review/today-summary" in src


def test_s1_forward_target_not_from_request_params() -> None:
    """转发目标不得从请求 query/body 读取（SSRF 防线静态断言）。"""
    from core.app import create_app

    import inspect

    src = inspect.getsource(create_app)
    # summary_today 不读取任何 query 参数作为目标
    assert "request.query_params" not in src.split("_SUMMARY_PROVIDERS")[1].split(
        "app.include_router"  # noqa: E501
    )[0]


# ── S-2 · token 透传 + 单家超时 + 不落日志 ───────────────────────────────
def test_s2_token_sent_to_provider_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """JWT 只透传给插件端点，不进 URL（url 由固定注册表拼接）。"""
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={})

    asyncio.run(
        _call_fetch(
            handler,
            headers={"Authorization": "Bearer caller-token-123"},
        )
    )
    assert "caller-token-123" not in captured["url"]  # 不进 URL
    assert captured["auth"] == "Bearer caller-token-123"  # 只进 header


def test_s2_single_provider_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """单家超时窗口存在（S-2：防 hang 放大）。"""
    from core.app import create_app

    import inspect

    src = inspect.getsource(create_app)
    assert "_SUMMARY_TIMEOUT" in src


def test_s3_audit_log_no_authorization(monkeypatch: pytest.MonkeyPatch) -> None:
    """审计日志不含 Authorization（S-3：token 不落日志）。"""
    from core.app import create_app

    import inspect

    src = inspect.getsource(create_app)
    # 定位审计日志的 extra 行：只记 providers 状态映射
    prov_line = [
        l
        for l in src.splitlines()
        if '"providers"' in l and "extra" in l
    ]
    assert prov_line, "应存在审计日志 extra 行（providers 状态映射）"
    line = prov_line[0]
    # 日志不得引用 auth/header/token（S-3：token 不落日志）
    assert "headers" not in line and "auth" not in line
    assert "Authorization" not in line and "token" not in line