"""push 插件测试（Web Push：订阅/注销/刷新/广播兜错/410 清理/API 面）。

数据库隔离：临时库 ./data/tmp_push.db，绝不碰主库 lifos.db（test_notes 先例）。
外发 HTTP 全部 mock —— 没有真推送服务，不伪造「已推送」。
"""
from __future__ import annotations

import os

os.environ["DB_PATH"] = "./data/tmp_push.db"


import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session, select  # noqa: E402

from core.app import create_app  # noqa: E402
from core.security import create_access_token  # noqa: E402
from db.engine import get_engine, init_engine  # noqa: E402
from db.models.system import PluginState  # noqa: E402
from modules.push import push_link, sender  # noqa: E402
from modules.push.models import PushLog, PushSubscription  # noqa: E402

ENDPOINT = "https://push.example.test/subscribe/abc123def456"


@pytest.fixture(scope="module", autouse=True)
def _schema():
    """★ 建表必须与 client fixture 解耦（实测踩过）：本文件有只请求 db 的测试，
    它们同样会走 autouse 的 _clean；而 client 是 module fixture，只有请求它的
    测试才会触发 —— 建表若挂在 client 上，这些测试就在 _clean 里撞
    "no such table: push_subscription"（6 个 ERROR 的真实根因）。
    plugin_state 是 /api/v1/plugins 的内核表，一并建（本仓库 fixture 建表的既定做法）。"""
    init_engine()
    engine = get_engine()
    PushSubscription.__table__.create(bind=engine, checkfirst=True)
    PushLog.__table__.create(bind=engine, checkfirst=True)
    PluginState.__table__.create(bind=engine, checkfirst=True)
    yield
    engine.dispose()


@pytest.fixture(scope="module")
def client():
    yield TestClient(create_app())


@pytest.fixture(autouse=True)
def _clean():
    engine = get_engine()
    with Session(engine) as s:
        for row in s.exec(select(PushSubscription)).all():
            s.delete(row)
        for row in s.exec(select(PushLog)).all():
            s.delete(row)
        s.commit()
    yield


@pytest.fixture()
def db():
    with Session(get_engine()) as s:
        yield s


def _auth() -> dict[str, str]:
    tk = create_access_token('admin')
    return {"Authorization": "Bearer " + tk}


# ────────────────────────── service 层 ──────────────────────────

def test_subscribe_then_list(db: Session) -> None:
    row = sender.subscribe(
        db, {"endpoint": ENDPOINT, "keys": {"p256dh": "BK" + "x" * 80, "auth": "authtoken"}}
    )
    assert row.active is True
    assert sender.list_active(db)[0].endpoint == ENDPOINT


def test_resubscribe_refreshes_keys_and_revives(db: Session) -> None:
    sender.subscribe(db, {"endpoint": ENDPOINT, "keys": {"p256dh": "BK1xx", "auth": "a1"}})
    assert sender.unsubscribe(db, ENDPOINT) is True
    assert sender.list_active(db) == []
    row = sender.subscribe(db, {"endpoint": ENDPOINT, "keys": {"p256dh": "BK2xx", "auth": "a2"}})
    assert row.active is True and row.p256dh == "BK2xx"  # 复活+换key，不重复登记


def test_subscribe_missing_fields_rejected(db: Session) -> None:
    from core.errors import ValidationError
    with pytest.raises(ValidationError):
        sender.subscribe(db, {"endpoint": ENDPOINT, "keys": {"p256dh": "", "auth": ""}})


def test_send_without_vapid_reports_not_configured(db: Session, monkeypatch) -> None:
    monkeypatch.setattr(sender, "vapid_ready", lambda: False)
    out = sender.send_broadcast(db, title="测试")
    assert out["ok"] is False and "未配置" in (out["detail"] or "")
    row = db.exec(select(PushLog)).first()
    assert row is not None and row.ok is False  # 失败也留审计


def test_send_prunes_gone_subscriptions(db: Session, monkeypatch) -> None:
    sender.subscribe(db, {"endpoint": ENDPOINT, "keys": {"p256dh": "BK", "auth": "a"}})
    monkeypatch.setattr(sender, "vapid_ready", lambda: True)
    monkeypatch.setattr(sender, "pywebpush_available", lambda: True)
    monkeypatch.setattr(sender, "_send_one", lambda sub, t, b, u, tag: (False, 410, "Gone"))
    out = sender.send_broadcast(db, title="测试")
    assert out["pruned"] == 1 and out["ok"] is False
    assert sender.list_active(db) == []


def test_send_ok_counts(db: Session, monkeypatch) -> None:
    sender.subscribe(db, {"endpoint": ENDPOINT, "keys": {"p256dh": "BK", "auth": "a"}})
    monkeypatch.setattr(sender, "vapid_ready", lambda: True)
    monkeypatch.setattr(sender, "pywebpush_available", lambda: True)
    monkeypatch.setattr(sender, "_send_one", lambda sub, t, b, u, tag: (True, 201, ""))
    out = sender.send_broadcast(db, title="测试", topic="manual")
    assert out["ok"] is True and out["sent"] == 1
    row = db.exec(select(PushLog)).first()
    assert row is not None and row.ok is True and row.topic == "manual"


# ────────────────────────── API 面（create_app 全栈挂载） ──────────────────────────

def test_api_health(client: TestClient) -> None:
    h = client.get("/api/v1/push/health")
    assert h.status_code == 200
    body = h.json()
    assert body["ok"] is True
    assert set(body) >= {"enabled", "vapid_ready", "pywebpush_installed", "subscriptions_active"}


def test_api_subscribe_flow(client: TestClient) -> None:
    r = client.post("/api/v1/push/subscribe", json={
        "endpoint": ENDPOINT, "keys": {"p256dh": "BK" + "y" * 80, "auth": "authzz"}})
    assert r.status_code == 200 and r.json()["active"] is True

    lst = client.get("/api/v1/push/subscriptions", headers=_auth())
    assert lst.status_code == 200 and len(lst.json()) == 1
    # ★ 响应零泄密：完整 endpoint 不出现在列表里
    assert ENDPOINT not in lst.text

    unsub = client.request("DELETE", "/api/v1/push/subscribe", params={"endpoint": ENDPOINT})
    assert unsub.status_code == 200 and unsub.json()["ok"] is True
    lst2 = client.get("/api/v1/push/subscriptions", headers=_auth())
    assert lst2.json()[0]["active"] is False


def test_api_requires_login_for_admin_endpoints(client: TestClient) -> None:
    assert client.get("/api/v1/push/subscriptions").status_code == 401
    assert client.post("/api/v1/push/send", json={"title": "x"}).status_code == 401


def test_reminder_event_triggers_push(client: TestClient, db: Session, monkeypatch) -> None:
    """事件联动：publish calendar.reminder.fired → push 通道被调用（ISSUE-007 同款验证）。

    ★ monkeypatch 必须打在 push_link 的命名空间上：push_link 用
      `from .sender import send_broadcast` 把函数对象绑进了自己的模块属性，
      改 sender.send_broadcast 打不中它（实测 calls 恒空、事件日志却已打出）。"""
    from core.events import event_bus

    calls: list[dict] = []
    monkeypatch.setattr(
        push_link,
        "send_broadcast",
        lambda db_, **kw: (
            calls.append(kw),
            {"ok": True, "sent": 0, "pruned": 0, "detail": None},
        )[1],
    )
    event_bus.publish("calendar.reminder.fired",
                      {"event_id": "e1", "title": "体检", "start_at": "2026-09-23T09:00:00+08:00"},
                      source="calendar")
    assert calls and "日程提醒" in calls[0]["title"]


def test_manifest_registers_and_mcp_tool_visible(client: TestClient) -> None:
    """push 插件过内核三层校验成功挂载 + provides 机械映射进 MCP（18 号判据）。

    ★ /api/v1/plugins 的响应是 {"plugins": [...]} 包装（与前端 PluginContext 一致），
      不是裸数组 —— 原写法 plugins.json() 直接迭代会 TypeError。
    """
    plugins = client.get("/api/v1/plugins", headers=_auth())
    assert plugins.status_code == 200
    ids = {p["id"] for p in plugins.json()["plugins"]}
    assert "push" in ids

    # provides 机械映射（T18 派生规则）：push.subscription.read → push_subscription_read
    tools = client.get("/api/v1/mcp/tools", headers=_auth())
    assert tools.status_code == 200
    names = {t["name"] for t in tools.json()}
    assert "push_subscription_read" in names, (
        "provides 未映射进 MCP；当前 push_* 工具："
        f"{sorted(n for n in names if n.startswith('push'))}"
    )
