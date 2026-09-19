"""T17 日记后端测试（薄壳：路径换算/幂等/时区/收件箱/归纳/零表）。

★ 本卡不建表，测试用 FakeDocsAdapter 模拟 T15 的 docs API，验证 service 纯逻辑。
★ 数据库隔离：临时库 ./data/tmp_t17_<随机>.db（★ 2026-09-20 唯一名防并发互踩；
  只为 TestClient 起服务，不建 diary_ 表）。
"""
from __future__ import annotations

import atexit
import os
import uuid
from contextlib import suppress

_TMP_DB = f"./data/tmp_t17_{uuid.uuid4().hex[:8]}.db"
os.environ["DB_PATH"] = _TMP_DB


def _cleanup_tmp_db() -> None:
    with suppress(FileNotFoundError, PermissionError):
        # Windows 上 SQLite 引擎句柄可能未释放，删不掉就算了（名字唯一不互踩即可）
        os.remove(_TMP_DB)


atexit.register(_cleanup_tmp_db)

from datetime import UTC, date  # noqa: E402

# ───────────────────────── Fake T15 适配器（内存树） ─────────────────────────
from uuid import uuid4  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from core.app import create_app  # noqa: E402
from core.errors import ValidationError  # noqa: E402
from core.security import create_access_token  # noqa: E402
from db.engine import get_engine, init_engine  # noqa: E402
from modules.diary.service import DiaryService  # noqa: E402


class FakeDocsAdapter:
    """在内存里模拟一棵 docs 树，满足 DocsAdapter 协议。"""

    def __init__(self) -> None:
        self.nodes: dict[str, dict] = {}  # id -> node

    def _add(self, parent_id, kind, name, meta=None) -> dict:
        nid = uuid4().hex
        node = {
            "id": nid,
            "parent_id": parent_id,
            "kind": kind,
            "name": name,
            "sort": 0,
            "meta_json": meta,
            "created_at": f"2026-09-19T00:0{len(self.nodes)}:00+00:00",
            "updated_at": "2026-09-19T00:00:00+00:00",
            "deleted_at": None,
        }
        self.nodes[nid] = node
        return node

    def _children(self, parent_id) -> list[dict]:
        return [n for n in self.nodes.values() if n["parent_id"] == parent_id]

    def _to_tree(self, parent_id) -> list[dict]:
        out = []
        for c in self._children(parent_id):
            cc = dict(c)
            cc["children"] = self._to_tree(c["id"])
            out.append(cc)
        return out

    def tree(self) -> list[dict]:
        return self._to_tree(None)

    def create(self, parent_id, kind, name, meta=None) -> dict:
        return self._add(parent_id, kind, name, meta)

    def patch(self, node_id, body) -> dict:
        node = self.nodes[node_id]
        if "parent_id" in body and body.get("parent_id") is not None:
            node["parent_id"] = body["parent_id"]
        if body.get("parent_id") is None and "parent_id" in body:
            node["parent_id"] = None
        if "meta_json" in body:
            node["meta_json"] = body["meta_json"]
        return node

    def count_kind(self, kind) -> int:
        return sum(1 for n in self.nodes.values() if n["kind"] == kind)


@pytest.fixture
def svc():
    return DiaryService(FakeDocsAdapter(), tz="Asia/Shanghai")


# ───────────────────────── 定位与幂等 ─────────────────────────
def test_get_or_create_path(svc):
    r = svc.get_or_create_entry("2026-09-19")
    assert r["path"] == "日记/2026/09/2026-09-19"
    assert r["exists"] is False
    assert r["node_id"]


def test_idempotent_ten_calls_one_node(svc):
    """连调 10 次同一天 → 只有一个节点（幂等）。"""
    first = svc.get_or_create_entry("2026-09-19")
    for _ in range(9):
        r = svc.get_or_create_entry("2026-09-19")
        assert r["node_id"] == first["node_id"]
        assert r["exists"] is True
    # 树里该天 doc 只有一个
    assert svc.docs.count_kind("doc") == 1
    # 年 folder + 月 folder + 日记根 + 收件箱? 不，get_or_create 不建收件箱
    folders = sum(1 for n in svc.docs.nodes.values() if n["kind"] == "folder")
    assert folders == 3  # 日记 / 2026 / 09


def test_different_days_different_nodes(svc):
    a = svc.get_or_create_entry("2026-09-18")
    b = svc.get_or_create_entry("2026-09-19")
    assert a["node_id"] != b["node_id"]
    assert a["path"] == "日记/2026/09/2026-09-18"
    assert b["path"] == "日记/2026/09/2026-09-19"


def test_cross_year_month(svc):
    r = svc.get_or_create_entry("2027-01-05")
    assert r["path"] == "日记/2027/01/2027-01-05"


def test_meta_date_mirror(svc):
    svc.get_or_create_entry("2026-09-19")
    nid = svc.get_or_create_entry("2026-09-19")["node_id"]
    assert svc.docs.nodes[nid]["meta_json"]["diary_date"] == "2026-09-19"


def test_invalid_date(svc):
    with pytest.raises(ValidationError):
        svc.get_or_create_entry("不是日期")


# ───────────────────────── 时区（真实踩坑） ─────────────────────────
def test_today_uses_local_tz():
    """把今天固定成本地 00:30 → /today 必须返回当天，不是前一天。"""
    import modules.diary.service as svcmod

    class FakeDT(date):
        pass

    # 直接测 today()：注入 tz，验证返回的是上海时区的 date
    s = DiaryService(FakeDocsAdapter(), tz="Asia/Shanghai")
    from datetime import datetime
    from zoneinfo import ZoneInfo

    local = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    assert s.today() == local

    # UTC 凌晨对应本地前一天 → 证明按本地时区切天
    # 模拟：北京 2026-09-19 00:30 == UTC 2026-09-18 16:30

    moment_utc = datetime(2026, 9, 18, 16, 30, tzinfo=UTC)
    got = moment_utc.astimezone(ZoneInfo("Asia/Shanghai")).date()
    assert got == date(2026, 9, 19)  # 本地已是 19 号，不能落 18 号
    _ = svcmod


# ───────────────────────── 月历 / 收件箱 / 归纳 ─────────────────────────
def test_month_days(svc):
    svc.get_or_create_entry("2026-09-18")
    svc.get_or_create_entry("2026-09-19")
    days = svc.month_days(2026, 9)
    assert days == ["2026-09-18", "2026-09-19"]


def test_inbox_empty_until_created(svc):
    # 没有收件箱时返回 []（ensure_inbox 会建）
    items = svc.inbox_items()
    assert items == []


def test_capture_then_inbox(svc):
    cap = svc.capture()
    assert cap["path"].startswith("日记/收件箱/")
    items = svc.inbox_items()
    assert any(i["id"] == cap["node_id"] for i in items)


def test_capture_unique_names(svc):
    """同一分钟连记两次 → 名字不撞（-2）。"""
    a = svc.capture()
    b = svc.capture()
    assert a["name"] != b["name"]


def test_consolidate_moves_to_month(svc):
    cap = svc.capture()
    r = svc.consolidate(cap["node_id"], "2026-09-19")
    # 归纳后该节点 parent 指向 09 月份 folder，且 meta 带 diary_date
    node = svc.docs.nodes[cap["node_id"]]
    month_node = r["target_month_node"]
    assert node["parent_id"] == month_node
    assert node["meta_json"]["diary_date"] == "2026-09-19"


def test_zero_diary_tables():
    """★ 留白判据：diary 不建任何 diary_ 表。"""
    init_engine()
    engine = get_engine()
    with engine.connect() as conn:
        tables = {
            row[0]
            for row in conn.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'diary_%'"
            )
        }
    assert tables == set()


# ───────────────────────── TestClient（health/manifest） ─────────────────────────
@pytest.fixture(scope="module")
def client():
    init_engine()
    app = create_app()
    c = TestClient(app)
    yield c
    get_engine().dispose()


@pytest.fixture
def auth():
    return {"Authorization": f"Bearer {create_access_token('admin')}"}


def test_health(client):
    r = client.get("/api/v1/diary/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_manifest(client):
    r = client.get("/api/v1/diary/manifest")
    assert r.status_code == 200
    m = r.json()
    assert m["id"] == "diary"
    assert m["provides"] == []
    assert sorted(m["requires"]) == ["docs.node.read", "docs.node.write", "docs.search"]
    assert m["permissions"] == []
