"""T11 dashboard 后端测试。

数据库隔离：./data/tmp_t11_dashboard.db，绝不碰主库。
聚合 HTTP：mock modules.dashboard.aggregator 的 fetch，不要求真起 8000。
"""
from __future__ import annotations

import asyncio
import os
from typing import Any

os.environ["DB_PATH"] = "./data/tmp_t11_dashboard.db"
os.environ["DASHBOARD_SELF_BASE"] = "http://127.0.0.1:8000"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from core.app import create_app  # noqa: E402
from core.security import create_access_token  # noqa: E402
from db.engine import get_engine, init_engine  # noqa: E402
from modules.dashboard import aggregator as agg  # noqa: E402

BASE = "/api/v1/dashboard"


# ───────────────────────── mock fetch ─────────────────────────
def _default_ok_routes() -> dict[str, Any]:
    return {
        "/api/v1/calendar/health": {"ok": True},
        "/api/v1/todo/health": {"ok": True},
        "/api/v1/habits/health": {"ok": True},
        "/api/v1/finance/health": {"ok": True},
        "/api/v1/review/health": {"ok": True},
        "/api/v1/agents/health": {"ok": True},
        "/api/v1/todo/summary": {"today": 3, "overdue": 1, "week_done": 5},
        "/api/v1/habits/summary": {
            "total": 4,
            "done": 2,
            "pending": 2,
            "rest": 0,
            "best_streak": 7,
        },
        "/api/v1/finance/snapshots": {
            "items": [
                {
                    "id": "s1",
                    "date": "2026-09-18",
                    "total_asset": 123456,
                    "cash": 23456,
                    "invest": 100000,
                    "debt": 0,
                }
            ],
            "total": 1,
            "limit": 1,
            "offset": 0,
        },
        "/api/v1/finance/summary": {
            "expense_cents": 1000,
            "income_cents": 2000,
            "net_cents": 1000,
            "count": 2,
        },
        "/api/v1/review/source": {
            "mode": "mock",
            "path": "mock",
            "bridge": False,
            "upstream_online": True,
            "message": "ok",
        },
        "/api/v1/plugins": {
            "plugins": [
                {
                    "id": "calendar",
                    "name": "日程表",
                    "slots": ["dashboard.card"],
                    "enabled": True,
                    "valid": True,
                },
                {
                    "id": "todo",
                    "name": "todo",
                    "slots": ["dashboard.card"],
                    "enabled": True,
                    "valid": True,
                },
                {
                    "id": "habits",
                    "name": "习惯打卡",
                    "slots": ["dashboard.card"],
                    "enabled": True,
                    "valid": True,
                },
                {
                    "id": "agents",
                    "name": "AI 编排",
                    "slots": ["dashboard.card"],
                    "enabled": True,
                    "valid": True,
                },
                {
                    "id": "finance",
                    "name": "理财",
                    "slots": [],
                    "enabled": True,
                    "valid": True,
                },
            ],
            "count": 5,
        },
    }


def _calendar_events() -> list[dict[str, Any]]:
    return [
        {
            "id": "e1",
            "title": "上课 · 无机化学",
            "start_at": "2026-09-18T08:00:00+08:00",
            "end_at": "2026-09-18T10:00:00+08:00",
            "all_day": False,
        },
        {
            "id": "e2",
            "title": "眼保健操",
            "start_at": "2026-09-18T09:30:00+08:00",
            "end_at": "2026-09-18T09:40:00+08:00",
            "all_day": False,
        },
    ]


def make_fetch(routes: dict[str, Any] | None = None) -> Any:
    table = routes if routes is not None else _default_ok_routes()
    calls: list[str] = []

    async def _fetch(path: str) -> Any:
        calls.append(path)
        key = path.split("?")[0]
        if key == "/api/v1/calendar/events":
            return _calendar_events()
        if key not in table:
            raise RuntimeError(f"unexpected path: {path}")
        return table[key]

    _fetch.calls = calls  # type: ignore[attr-defined]
    return _fetch


@pytest.fixture(scope="module")
def client():
    init_engine()
    engine = get_engine()
    app = create_app()
    c = TestClient(app)
    yield c
    engine.dispose()


@pytest.fixture(autouse=True)
def _reset_fetch():
    agg.set_fetch_override(None)
    yield
    agg.set_fetch_override(None)


@pytest.fixture
def auth():
    return {"Authorization": f"Bearer {create_access_token('admin')}"}


@pytest.fixture
def mock_ok(client, auth):
    """挂上全绿 mock，并顺便确认 overview 可用。"""
    fetch = make_fetch()
    agg.set_fetch_override(fetch)
    return fetch


# ───────────────────────── 基础 ─────────────────────────
def test_health(client):
    r = client.get(f"{BASE}/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_manifest(client):
    r = client.get(f"{BASE}/manifest")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "dashboard"
    assert body["kind"] == "builtin"
    assert body["api"]["base"] == "/api/v1/dashboard"
    assert body["migrations"] is None
    assert "dashboard.overview.read" in body["provides"]


def test_no_auth(client):
    for path in ("/overview", "/today", "/health-of-system", "/growth"):
        r = client.get(f"{BASE}{path}")
        assert r.status_code in (401, 403), f"{path} 应无鉴权拒绝，实际 {r.status_code}"


# ───────────────────────── overview 结构 ─────────────────────────
def test_overview_structure(client, auth, mock_ok):
    r = client.get(f"{BASE}/overview", headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()

    # 必备字段
    for key in ("date", "today", "money", "review", "growth", "system", "cards", "cards_hint"):
        assert key in body, f"overview 缺字段 {key}"

    assert isinstance(body["date"], str) and len(body["date"]) >= 8

    # today counts ← 上游真实字段（mock 里写死的测试数据，不是硬编码在产品代码里）
    counts = body["today"]["counts"]
    assert counts["calendar_events"] == 2
    assert counts["todo_open"] == 3
    assert counts["habits_done"] == 2
    assert counts["habits_total"] == 4

    # 上游 path 可追溯（零硬编码自检）
    paths = body["meta"]["upstream_paths"]
    assert "/api/v1/todo/summary" in paths["todo_summary"]
    assert "/api/v1/habits/summary" in paths["habits_summary"]
    assert "/api/v1/finance/snapshots" in paths["finance_snapshots"]
    assert "/api/v1/review/source" in paths["review_source"]

    # money：快照来自 finance snapshots
    snap = body["money"]["snapshot"]
    assert snap["status"] == "ok"
    assert snap["total_asset"] == 123456

    # review source
    assert body["review"]["source"]["mode"] == "mock"

    # growth 占位
    assert body["growth"]["axes"] == []
    assert body["growth"]["placeholder"]

    # system：六个模块全 ok
    ids = [s["id"] for s in body["system"]]
    for mid in ("calendar", "todo", "habits", "finance", "review", "agents"):
        assert mid in ids
    assert all(s["status"] == "ok" for s in body["system"])

    # cards 提示：声明 dashboard.card 的插件（不含 finance）
    card_ids = [c["pluginId"] for c in body["cards"]]
    assert "calendar" in card_ids
    assert "todo" in card_ids
    assert "habits" in card_ids
    assert "agents" in card_ids
    assert "finance" not in card_ids
    assert "SlotHost" in body["cards_hint"]


def test_overview_parallel_calls_upstream(client, auth, mock_ok):
    r = client.get(f"{BASE}/overview", headers=auth)
    assert r.status_code == 200
    # mock 确实打到了各上游路径
    assert any(c.startswith("/api/v1/calendar/events") for c in mock_ok.calls)
    assert "/api/v1/todo/summary" in mock_ok.calls
    assert "/api/v1/habits/summary" in mock_ok.calls
    assert "/api/v1/plugins" in mock_ok.calls
    assert "/api/v1/calendar/health" in mock_ok.calls


# ───────────────────────── 降级：单模块失败仍 200 ─────────────────────────
def test_overview_single_module_error_still_200(client, auth):
    routes = _default_ok_routes()

    async def fetch(path: str) -> Any:
        key = path.split("?")[0]
        if key == "/api/v1/todo/summary":
            raise RuntimeError("todo down")
        if key == "/api/v1/calendar/events":
            return _calendar_events()
        return routes[key]

    agg.set_fetch_override(fetch)
    r = client.get(f"{BASE}/overview", headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()

    todo = body["today"]["todo"]
    assert todo["status"] == "error"
    assert body["today"]["counts"]["todo_open"] is None
    # 其余照常
    assert body["today"]["counts"]["habits_done"] == 2
    assert body["today"]["counts"]["calendar_events"] == 2
    assert body["money"]["snapshot"]["total_asset"] == 123456


def test_overview_timeout_degrades(client, auth):
    routes = _default_ok_routes()

    async def fetch(path: str) -> Any:
        key = path.split("?")[0]
        if key == "/api/v1/habits/summary":
            await asyncio.sleep(2.0)  # 远超 800ms
            return routes[key]
        if key == "/api/v1/calendar/events":
            return _calendar_events()
        return routes[key]

    agg.set_fetch_override(fetch)
    r = client.get(f"{BASE}/overview", headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    habits = body["today"]["habits"]
    assert habits["status"] == "timeout"
    assert body["today"]["counts"]["habits_done"] is None
    assert body["today"]["counts"]["todo_open"] == 3
    # system 里 habits health 仍是 ok（health 路径没超时）
    by_id = {s["id"]: s for s in body["system"]}
    assert by_id["habits"]["status"] == "ok"


def test_overview_health_timeout_marks_system(client, auth):
    routes = _default_ok_routes()

    async def fetch(path: str) -> Any:
        key = path.split("?")[0]
        if key == "/api/v1/finance/health":
            raise TimeoutError("slow")
        if key == "/api/v1/calendar/events":
            return _calendar_events()
        return routes[key]

    agg.set_fetch_override(fetch)
    r = client.get(f"{BASE}/overview", headers=auth)
    assert r.status_code == 200
    body = r.json()
    by_id = {s["id"]: s for s in body["system"]}
    assert by_id["finance"]["status"] == "timeout"
    assert "finance" in body["meta"]["degraded"]
    # overview 仍完整
    assert body["today"]["counts"]["todo_open"] == 3


def test_overview_all_down_still_200(client, auth):
    async def fetch(path: str) -> Any:
        raise RuntimeError(f"everything down: {path}")

    agg.set_fetch_override(fetch)
    r = client.get(f"{BASE}/overview", headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["date"]
    assert all(s["status"] == "error" for s in body["system"])
    assert body["today"]["counts"]["calendar_events"] is None
    assert body["money"]["snapshot"]["status"] in ("error", "timeout")
    assert body["cards"] == []


# ───────────────────────── today / health-of-system / growth ─────────────────────────
def test_today(client, auth, mock_ok):
    r = client.get(f"{BASE}/today", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["date"]
    assert body["counts"]["todo_open"] == 3
    assert body["counts"]["habits_done"] == 2
    assert body["counts"]["habits_total"] == 4
    assert body["counts"]["calendar_events"] == 2


def test_health_of_system(client, auth, mock_ok):
    r = client.get(f"{BASE}/health-of-system", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert len(body["system"]) >= 6
    assert all(s["status"] == "ok" for s in body["system"])
    assert body["meta"]["timeout_ms"] == 800


def test_health_of_system_degraded(client, auth):
    async def fetch(path: str) -> Any:
        if path.endswith("/health") and "todo" in path:
            raise RuntimeError("todo health down")
        return {"ok": True}

    agg.set_fetch_override(fetch)
    r = client.get(f"{BASE}/health-of-system", headers=auth)
    assert r.status_code == 200
    body = r.json()
    by_id = {s["id"]: s for s in body["system"]}
    assert by_id["todo"]["status"] == "error"
    assert by_id["calendar"]["status"] == "ok"


def test_growth_placeholder(client, auth, mock_ok):
    r = client.get(f"{BASE}/growth", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["axes"] == []
    assert "后补" in body["placeholder"] or "罗盘" in body["placeholder"]


def test_aggregator_unit_timeout_status():
    """单测：不经过 HTTP 服务，直接测 _safe_call 超时语义。"""

    async def slow(path: str) -> Any:
        await asyncio.sleep(1.0)
        return {"ok": True}

    async def run() -> dict[str, Any]:
        return await agg._safe_call(slow, "/api/v1/x")

    result = asyncio.run(run())
    assert result["status"] == "timeout"
    assert result["path"] == "/api/v1/x"


def test_aggregator_unit_parallel_three():
    """单测：能同时调 3 个假接口。"""
    seen: list[str] = []

    async def fetch(path: str) -> Any:
        seen.append(path)
        await asyncio.sleep(0.05)
        return {"ok": True, "path": path}

    async def run() -> dict[str, Any]:
        return await agg.aggregate_overview(fetch=fetch)

    body = asyncio.run(run())
    assert body["date"]
    assert len(seen) >= 3
    assert any("calendar" in p for p in seen)
    assert any("todo" in p for p in seen)
    assert any("habits" in p for p in seen)
