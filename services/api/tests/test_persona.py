"""T16 人格体系后端测试（极薄：只验 health / manifest / 零业务字段）。

数据库隔离：临时库 ./data/tmp_t16_<随机>.db（★ 2026-09-20 唯一名防并发互踩）。
★ 薄壳不建表：本测试不建任何 persona_ 表，验证「persona 无业务表」这一判据。
"""
from __future__ import annotations

import atexit
import os
import uuid
from contextlib import suppress

# ★ 必须在 import 任何内核/模块之前设置临时库
_TMP_DB = f"./data/tmp_t16_{uuid.uuid4().hex[:8]}.db"
os.environ["DB_PATH"] = _TMP_DB


def _cleanup_tmp_db() -> None:
    with suppress(FileNotFoundError, PermissionError):
        # Windows 上 SQLite 引擎句柄可能未释放，删不掉就算了（名字唯一不互踩即可）
        os.remove(_TMP_DB)


atexit.register(_cleanup_tmp_db)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from core.app import create_app  # noqa: E402
from core.security import create_access_token  # noqa: E402
from db.engine import get_engine, init_engine  # noqa: E402


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
    r = client.get("/api/v1/persona/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_manifest_requires_docs(client):
    auth = {"Authorization": f"Bearer {create_access_token('admin')}"}
    r = client.get("/api/v1/persona/manifest", headers=auth)
    assert r.status_code == 200
    m = r.json()
    assert m["id"] == "persona"
    assert m["requires"] == ["docs.node.read", "docs.node.write", "docs.search"]
    assert m["provides"] == []
    assert m["permissions"] == []
    assert "desktop.dock" in m["slots"]


def test_no_persona_tables():
    """★ 留白判据：persona 不建任何业务表。"""
    engine = get_engine()
    with engine.connect() as conn:
        tables = {
            row[0]
            for row in conn.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'persona_%'"
            )
        }
    assert tables == set(), f"persona 不应有任何表，发现：{tables}"
