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


# ── S-1 · 转发目标来自 manifest 声明，不由请求参数决定（防 SSRF）──────────
# ★ 2026-09-25 语义化改写（astrbot · 事故响应）：
#   workbuddy `c2b03bf` 把 BFF 聚合源从「硬编码四家」改为「manifest 动态发现」
#   （符合 ADR-0003「一切皆插件」）。原判据断言「create_app 源码含四源字面量」，
#   重构后必然失效；且符号 `_SUMMARY_PROVIDERS` 已删 → 第二例 split() IndexError。
#   → 新判据**锚语义不锚字面量**：源集合 ⊆ 各模块 manifest 声明的 x.summary.today，
#     且转发目标不得来自请求参数（SSRF 防线语义不变）。
def test_s1_providers_come_from_manifest_declaration() -> None:
    """S-1：聚合源由 manifest 的 `x.summary.today` 声明决定，不由请求参数决定。"""
    from core.app import create_app

    import inspect

    src = inspect.getsource(create_app)
    # ① 语义：动态发现以 x.summary.today 为过滤条件（源集合 ⊆ manifest 声明）
    assert "x.summary.today" in src, "BFF 聚合源未按 manifest 声明发现"


def test_s1_forward_target_not_from_request_params() -> None:
    """S-1：转发目标路径由内核注册表拼接，不得来自请求 query/body（SSRF 静态断言）。"""
    from core.app import create_app

    import inspect

    src = inspect.getsource(create_app)
    seg = src.split("async def summary_today")[1].split("app.include_router")[0]
    # 转发目标来自注册表 _summary_providers，且端点不读请求参数作为目标
    assert "_summary_providers" in seg
    assert "request.query_params" not in seg
    assert "request.json()" not in seg


def test_s1_providers_non_empty_from_manifests() -> None:
    """★ 防「聚合源为空」复发（2026-09-25 事故）：四源 manifest 必须声明 x.summary.today。

    事故链：`c2b03bf` 改动态发现 → 四源未同步声明 → `_summary_providers` 为空
    → `/summary/today` 返回 `providers: []` → ② 小日历四分区无数据。
    本判据把「四源声明齐」变成机器可检，防止同类重构再留半截。
    """
    import json
    from pathlib import Path

    mods = Path(__file__).resolve().parents[1] / "modules"
    declared: set[str] = set()
    for mf in mods.glob("*/manifest.json"):
        try:
            d = json.loads(mf.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 - 坏 manifest 由别的判据管
            continue
        if "x.summary.today" in (d.get("provides") or []):
            declared.add(d.get("id") or mf.parent.name)
    required = {"calendar", "todo", "diary", "review"}
    missing = required - declared
    assert not missing, f"四源未全部声明 x.summary.today：缺 {sorted(missing)}"


# ── fail-soft · 聚合层「四源缺一不塌」（令 99 派单 · astrbot）──────────────
def test_failsoft_one_provider_down_others_still_return() -> None:
    """★ fail-soft：四源中一家/多家挂掉，其余源**仍正常返回**——「缺一不塌」。

    对照：R-1 系列测的是**单家**语义（404/5xx/网络错 → 各自三态）；
          本用例测的是**聚合层**语义（一家坏 ≠ 全坏，聚合不整体失败）。
    来源：总监令 99 §2「@astrbot：fail-soft 测试『四源缺一不塌』」。
    """

    async def run() -> list[dict[str, Any]]:
        # 四家并发，各挂各的：calendar 5xx / review 网络错 / todo+diary 正常
        handlers: dict[str, Any] = {
            "calendar": lambda req: httpx.Response(500, text="boom"),
            "todo": lambda req: httpx.Response(200, json={"title": "待办", "items": []}),
            "diary": lambda req: httpx.Response(
                200, json={"title": "日记", "items": [{"text": "x", "state": "info"}]}
            ),
            "review": lambda req: (_ for _ in ()).throw(httpx.ConnectError("down")),
        }

        async def one(pid: str, handler: Any) -> dict[str, Any]:
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(handler), base_url="http://t"
            ) as client:
                return await _fetch_one(
                    client, pid, f"http://t/api/v1/{pid}/today-summary", {}, 3.0
                )

        return list(await asyncio.gather(*(one(pid, h) for pid, h in handlers.items())))

    results = asyncio.run(run())
    by_id = {r["id"]: r for r in results}

    # ① 聚合不整体崩：四家条目都在
    assert len(results) == 4, "聚合层整体失败（缺一即塌）"
    # ② 坏的两家 → unavailable（各自标记，不抛异常）
    assert by_id["calendar"]["status"] == "unavailable"
    assert by_id["review"]["status"] == "unavailable"
    # ③ 好的两家 → ok，且 data 原样透传（R-1 不受影响）
    assert by_id["todo"]["status"] == "ok"
    assert by_id["diary"]["status"] == "ok"
    assert by_id["diary"]["data"] == {"title": "日记", "items": [{"text": "x", "state": "info"}]}
    # ④ 失败源不含 data 键（三态语义干净）
    assert "data" not in by_id["calendar"]
    assert "data" not in by_id["review"]


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