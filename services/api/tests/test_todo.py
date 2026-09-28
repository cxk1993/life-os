"""T06 待办与周期清单后端测试（只跑这一个文件，不影响别的卡）。

数据库隔离：用临时库 ./data/tmp_t06.db，绝不碰主库 lifos.db。
表只在当前进程内由模型直接建（create_app 不自动跑迁移，避免跨插件迁移碰撞）。
"""
from __future__ import annotations

import os

# ★ 必须在 import 任何内核/模块之前设置临时库，init_engine 只认一次。
os.environ["DB_PATH"] = "./data/tmp_t06.db"

from datetime import datetime, timedelta, timezone  # noqa: E402
from zoneinfo import ZoneInfo  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session, text  # noqa: E402

from core.app import create_app  # noqa: E402
from core.security import create_access_token  # noqa: E402
from db.engine import get_engine, init_engine  # noqa: E402
from db.todo_parser import parse_todo_line, to_todo_line  # noqa: E402
from modules.todo.models import TodoItem  # noqa: E402

TZ = timezone(timedelta(hours=8))  # 主人本地时区 Asia/Shanghai


@pytest.fixture(scope="module")
def client():
    init_engine()  # 用 DB_PATH 指向的临时库
    engine = get_engine()
    # 只建本插件一张表（单一模块实例，避免与迁移的 file-path 加载重复注册）。
    TodoItem.__table__.create(bind=engine, checkfirst=True)
    app = create_app()
    c = TestClient(app)
    yield c
    engine.dispose()


@pytest.fixture(autouse=True)
def _clean():
    """每条测试前清空本插件表，测试之间不得相互依赖。"""
    engine = get_engine()
    with Session(engine) as s:
        s.exec(text("DELETE FROM todo_item"))
        s.commit()
    yield


@pytest.fixture
def auth():
    return {"Authorization": f"Bearer {create_access_token('admin')}"}


def _iso(dt: datetime) -> str:
    return dt.astimezone(TZ).isoformat()


def _create(client, auth, **kw):
    r = client.post("/api/v1/todo/items", json=kw, headers=auth)
    assert r.status_code == 201, r.text
    return r.json()


def _today_within(hours_ahead: int = 2):
    """★ 2026-09-25 修（TX-FRAME-01 第⑦刀顺带）：造一个**保证落在今天**的未来时刻。

    背景（实测）：原写法 `datetime.now(TZ) + timedelta(hours=2)` 在 **22:00 之后**跑
    会落到**次日** —— 于是 today-summary 自然查不到它，测试变成
    「每晚 22 点后必失败」的时间 flaky（本席 22:47 跑全量时撞上）。

    语义保持：仍是"今天之内的未来时刻"（若 now+hours 跨天，则钳到当天 23:59）。
    """
    now = datetime.now(TZ)
    target = now + timedelta(hours=hours_ahead)
    if target.date() != now.date():
        target = now.replace(hour=23, minute=59, second=0, microsecond=0)
    return target


# ───────────────────────── 基础 ─────────────────────────
def test_health(client):
    r = client.get("/api/v1/todo/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_manifest(client):
    r = client.get("/api/v1/todo/manifest")
    assert r.status_code == 200
    m = r.json()
    assert m["id"] == "todo"
    assert "todo.item.created" in m["emits"]
    assert "dashboard.card" in m["slots"]


# ───────────────────────── CRUD ─────────────────────────
def test_create_and_get(client, auth):
    item = _create(client, auth, text="买牛奶")
    assert item["text"] == "买牛奶"
    assert item["done"] is False
    iid = item["id"]

    r = client.get(f"/api/v1/todo/items/{iid}", headers=auth)
    assert r.status_code == 200
    assert r.json()["text"] == "买牛奶"


def test_update(client, auth):
    item = _create(client, auth, text="初稿", priority="low")
    iid = item["id"]
    r = client.patch(
        f"/api/v1/todo/items/{iid}",
        json={"priority": "high", "text": "终稿"},
        headers=auth,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["priority"] == "high"
    assert body["text"] == "终稿"

    # 更新会发 todo.item.updated 事件（service 层 publish，不读流，只验证逻辑可跑）
    r2 = client.get(f"/api/v1/todo/items/{iid}", headers=auth)
    assert r2.json()["priority"] == "high"


def test_delete_204(client, auth):
    item = _create(client, auth, text="临时")
    iid = item["id"]
    r = client.delete(f"/api/v1/todo/items/{iid}", headers=auth)
    assert r.status_code == 204
    r2 = client.get(f"/api/v1/todo/items/{iid}", headers=auth)
    assert r2.status_code == 404


# ───────────────────────── 完成 / 取消 / 周期 ─────────────────────────
def test_toggle_completes_and_cancels(client, auth):
    item = _create(client, auth, text="写周报")
    iid = item["id"]
    r = client.post(f"/api/v1/todo/items/{iid}/toggle", headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["done"] is True
    assert body["done_at"] is not None

    r = client.post(f"/api/v1/todo/items/{iid}/toggle", headers=auth)
    assert r.status_code == 200
    assert r.json()["done"] is False
    assert r.json()["done_at"] is None


def test_recurring_spawns_next_instance_and_keeps_history(client, auth):
    # 2026-09-20 是周日；周期规则 FREQ=WEEKLY;BYDAY=SU
    due = _iso(datetime(2026, 9, 20, 9, 0, tzinfo=TZ))
    item = _create(client, auth, text="每周备份", due_at=due, recur_rule="FREQ=WEEKLY;BYDAY=SU")
    iid = item["id"]

    r = client.post(f"/api/v1/todo/items/{iid}/toggle", headers=auth)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["done"] is True
    assert out["next_id"] is not None, "周期任务完成应生成下一条实例"
    assert out["next_due_at"] is not None

    # 历史保留：原记录仍在且已 done；新实例 instance_no=1
    orig = client.get(f"/api/v1/todo/items/{iid}", headers=auth).json()
    assert orig["done"] is True
    nxt = client.get(f"/api/v1/todo/items/{out['next_id']}", headers=auth).json()
    assert nxt["instance_no"] == 1
    assert nxt["done"] is False
    # 下一次 = 7 天后的周日
    next_due = datetime.fromisoformat(nxt["due_at"])
    assert (next_due - datetime.fromisoformat(orig["due_at"])).days == 7

    # 整条链两条都在
    lst = client.get("/api/v1/todo/items", headers=auth).json()
    assert len(lst["items"]) == 2


# ───────────────────────── todo_parser 往返幂等 ─────────────────────────
def test_parser_owner_example_roundtrip():
    line = "- [ ] 每周备份 (@2026-10-01) 🔺 🔁 every week on Sunday"
    tl = parse_todo_line(line)
    assert tl.done is False
    assert tl.text == "每周备份"
    assert tl.due_at.isoformat() == "2026-10-01"
    assert tl.priority == "high"
    assert tl.recur_rule == "FREQ=WEEKLY;BYDAY=SU"

    # 往返：解析 → 还原 → 再解析，字段一致
    back = to_todo_line(tl)
    again = parse_todo_line(back)
    assert again.text == tl.text
    assert again.due_at == tl.due_at
    assert again.priority == tl.priority
    assert again.recur_rule == tl.recur_rule


def test_parser_recur_rule_roundtrip():
    # RRULE ↔ 人话 双向一致
    tl = parse_todo_line("- [ ] x 🔁 every week on Sunday")
    line = to_todo_line(tl)
    again = parse_todo_line(line)
    assert again.recur_rule == "FREQ=WEEKLY;BYDAY=SU"

    tl = parse_todo_line("- [ ] x 🔁 every week on Monday")
    assert tl.recur_rule == "FREQ=WEEKLY;BYDAY=MO"
    line = to_todo_line(tl)
    assert "every week on monday" in line
    again = parse_todo_line(line)
    assert again.recur_rule == "FREQ=WEEKLY;BYDAY=MO"


# ───────────────────────── 快速添加语法糖 ─────────────────────────
def test_quick_add_sugar(client, auth):
    r = client.post(
        "/api/v1/todo/items",
        json={"raw": "写周报 @周五 !高 #副业"},
        headers=auth,
    )
    assert r.status_code == 201, r.text
    item = r.json()
    assert item["priority"] == "high"
    assert item["tags"] == ["副业"]
    # @周五 → 下一个周五（存储为 UTC，需按上海时区判断）
    sh = ZoneInfo("Asia/Shanghai")
    due = datetime.fromisoformat(item["due_at"]).astimezone(sh)
    assert due.weekday() == 4  # Friday


# ───────────────────────── 导入 / 导出 ─────────────────────────
def test_import_counts_match_file(client, auth):
    md = (
        "# 我的清单\n"
        "- [ ] 任务一\n"
        "- [x] 已完成任务\n"
        "这是一句普通说明，不是任务\n"
        "- [ ] 每周备份 (@2026-10-01) 🔺 🔁 every week on Sunday\n"
        "- [ ] 带标签 #副业 的事\n"
    )
    r = client.post(
        "/api/v1/todo/import",
        json={"content": md},
        headers=auth,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # 文件里任务行（- [ ] / - [x]）共 4 行
    assert body["lines"] == 4
    assert body["imported"] == 4

    # 主人那条真实语法的字段被正确解析
    sunday = next(i for i in body["items"] if "每周备份" in i["text"])
    assert sunday["priority"] == "high"
    assert sunday["recur_rule"] == "FREQ=WEEKLY;BYDAY=SU"
    # 带 #副业 标签的那条应正确解析出 tags
    tagged = next(i for i in body["items"] if "带标签" in i["text"])
    assert tagged["tags"] == ["副业"]


def test_export_roundtrip_markdown(client, auth):
    _create(client, auth, text="任务一")
    _create(client, auth, text="任务二")
    r = client.post("/api/v1/todo/export", json={"status": "todo"}, headers=auth)
    assert r.status_code == 200, r.text
    md = r.json()["markdown"]
    # 每行都能被解析回一条任务（除勾选状态外结构一致）
    lines = [line for line in md.splitlines() if line.strip().startswith("- [")]
    assert len(lines) == 2
    for line in lines:
        parse_todo_line(line)  # 不应抛异常


# ───────────────────────── 概览统计 ─────────────────────────
def test_summary_counts(client, auth):
    _create(client, auth, text="今天要做的", due_at=_iso(datetime.now(TZ)))
    _create(client, auth, text="明天的", due_at=_iso(datetime.now(TZ) + timedelta(days=1)))
    # 逾期：过去一周
    _create(client, auth, text="逾期项", due_at=_iso(datetime.now(TZ) - timedelta(days=3)))
    # 已完成：本周
    done = _create(client, auth, text="已完成", due_at=_iso(datetime.now(TZ)))
    client.post(f"/api/v1/todo/items/{done['id']}/toggle", headers=auth)

    r = client.get("/api/v1/todo/summary", headers=auth)
    assert r.status_code == 200, r.text
    s = r.json()
    assert s["today"] >= 1          # 今天要做的 + 逾期项（逾期计入今日待办）
    assert s["overdue"] == 1
    assert s["week_done"] == 1


# ───────────────────────── U2 today-summary（派工令 62）─────────────────────────
def test_today_summary_200_shape(client, auth):
    """今日到期 + 逾期 → items（alert 优先），今日完成 → done 计数。"""
    _create(client, auth, text="今天开会", due_at=_iso(_today_within(2)))
    _create(client, auth, text="昨天逾期", due_at=_iso(datetime.now(TZ) - timedelta(days=1)))
    done = _create(client, auth, text="已完成项", due_at=_iso(datetime.now(TZ)))
    client.post(f"/api/v1/todo/items/{done['id']}/toggle", headers=auth)

    r = client.get("/api/v1/todo/today-summary", headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    # 规范 v1：title / items<=5 / link
    assert "title" in body and body["title"] != ""
    assert "link" in body and body["link"] == "/todo"
    assert len(body["items"]) <= 5
    texts = [it["text"] for it in body["items"]]
    assert "今天开会" in texts
    assert "昨天逾期" in texts
    # 逾期在前且 state=alert；今日到期 state=due
    assert body["items"][0]["text"] == "昨天逾期"
    assert body["items"][0]["state"] == "alert"
    assert any(it["state"] == "due" for it in body["items"])
    # 今日完成数
    assert body["done"] == 1


def test_today_summary_empty(client, auth):
    """无今日待办 → 空结构（200，不抛错）。"""
    r = client.get("/api/v1/todo/today-summary", headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["items"] == []
    assert body["done"] == 0


def test_today_summary_requires_auth(client):
    """鉴权：无 token → 401。"""
    r = client.get("/api/v1/todo/today-summary")
    assert r.status_code == 401


# ───────────────────────── 排序 / 优先级 ─────────────────────────
def test_sort_priority_and_done_last(client, auth):
    soon = _iso(datetime.now(TZ) + timedelta(days=1))
    high = _create(client, auth, text="高优先", priority="high", due_at=soon)
    low = _create(client, auth, text="低优先", priority="low", due_at=soon)
    done = _create(client, auth, text="已完成", due_at=_iso(datetime.now(TZ)))
    client.post(f"/api/v1/todo/items/{done['id']}/toggle", headers=auth)

    r = client.get("/api/v1/todo/items?status=todo", headers=auth)
    items = r.json()["items"]
    ids = [i["id"] for i in items]
    assert ids.index(high["id"]) < ids.index(low["id"])  # 高优先在前
    # done 项不出现在 status=todo 列表
    assert done["id"] not in ids


# ───────────────────────── 分页 ─────────────────────────
def test_pagination_cursor(client, auth):
    for i in range(5):
        _create(client, auth, text=f"项{i}")
    r1 = client.get("/api/v1/todo/items?limit=2", headers=auth)
    assert r1.status_code == 200
    p1 = r1.json()
    assert len(p1["items"]) == 2
    assert p1["next_cursor"] is not None

    r2 = client.get(f"/api/v1/todo/items?limit=2&cursor={p1['next_cursor']}", headers=auth)
    p2 = r2.json()
    assert len(p2["items"]) == 2
    # 两页不重复
    assert {i["id"] for i in p1["items"]} & {i["id"] for i in p2["items"]} == set()


# ───────────────────────── 边界测试 ─────────────────────────
def test_boundary_empty_text_rejected(client, auth):
    r = client.post("/api/v1/todo/items", json={"text": ""}, headers=auth)
    assert r.status_code == 422


def test_boundary_chinese_ok(client, auth):
    r = client.post(
        "/api/v1/todo/items",
        json={"text": "上课 · 无机化学（中文测试）🎉"},
        headers=auth,
    )
    assert r.status_code == 201
    assert "<script>" not in r.json()["text"]


def test_boundary_long_text_rejected(client, auth):
    r = client.post(
        "/api/v1/todo/items",
        json={"text": "长" * 600},  # max_length=500
        headers=auth,
    )
    assert r.status_code == 422


def test_boundary_no_timezone_rejected(client, auth):
    r = client.post(
        "/api/v1/todo/items",
        json={"text": "无时区", "due_at": "2026-09-15T08:00:00"},  # naive
        headers=auth,
    )
    # to_utc 对 naive 抛 ValidationError → 422
    assert r.status_code in (400, 422), r.text


def test_boundary_no_auth_rejected(client):
    r = client.get("/api/v1/todo/items")
    assert r.status_code in (401, 403)


# ───────────────────────── 幂等 ─────────────────────────
def test_idempotency_key(client, auth):
    headers = {**auth, "Idempotency-Key": "test-key-001"}
    r1 = client.post("/api/v1/todo/items", json={"text": "幂等测试"}, headers=headers)
    assert r1.status_code == 201, r1.text
    r2 = client.post("/api/v1/todo/items", json={"text": "幂等测试"}, headers=headers)
    assert r2.status_code == 201, r2.text
    assert r2.headers.get("X-Idempotent-Replay") == "true"
    assert r1.json()["id"] == r2.json()["id"]


# ─────────── 标签汇总（2026-09-28 主人令：AI 要能一目了然地分类）───────────
def test_manifest_declares_tag_read(client):
    r = client.get("/api/v1/todo/manifest")
    assert r.status_code == 200
    assert "todo.tag.read" in r.json()["provides"]


def test_tag_summary_counts_open_and_done(client, auth):
    """每个标签的 未完成/已完成/总数；层级标签各记各的。"""
    _create(client, auth, text="看高数", tags=["学业", "学业/高数"])
    _create(client, auth, text="看化学", tags=["学业", "学业/化学原理"])
    a = _create(client, auth, text="已完成的", tags=["学业"])
    client.post(f"/api/v1/todo/items/{a['id']}/toggle", headers=auth)

    r = client.get("/api/v1/todo/tags", headers=auth)
    assert r.status_code == 200, r.text
    got = {x["tag"]: x for x in r.json()}
    assert got["学业"] == {"tag": "学业", "todo": 2, "done": 1, "total": 3}
    assert got["学业/高数"] == {"tag": "学业/高数", "todo": 1, "done": 0, "total": 1}
    assert got["学业/化学原理"]["total"] == 1


def test_tag_summary_orders_by_open_count(client, auth):
    """排序：未完成多的在前（AI 先看到手头最重的分类）。"""
    for _ in range(2):
        _create(client, auth, text="轻的", tags=["轻标签"])
    for _ in range(3):
        _create(client, auth, text="重的", tags=["重标签"])
    tags = [x["tag"] for x in client.get("/api/v1/todo/tags", headers=auth).json()]
    assert tags.index("重标签") < tags.index("轻标签")


def test_tag_summary_ignores_untagged_and_is_empty_when_none(client, auth):
    """无标签事项不进汇总；一条标签都没有时返回空数组（不是 404）。"""
    _create(client, auth, text="没标签的")
    r = client.get("/api/v1/todo/tags", headers=auth)
    assert r.status_code == 200 and r.json() == []


def test_tag_summary_requires_auth(client):
    assert client.get("/api/v1/todo/tags").status_code == 401
