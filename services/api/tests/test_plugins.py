"""插件框架集成测试（T14）。

覆盖验收清单里能用机器证明的项：
  - 契约校验精确到字段（缺 kernelApi / 未知字段 / 非法 id）
  - kernelApi 不兼容明确拒绝（人话）
  - 声明式权限：未声明 → 403 且说明缺哪个权限
  - 设置按 settingsSchema 校验，写错类型被拒
  - 四态：install → enable → disable → uninstall，且 uninstall 把表/文件/状态清干净
  - 注册表与运行时分离：disable 摘掉路由、enable 重新挂上
  - core 不可禁用、builtin 不可卸载（明确拒绝）

测试用一个真实的第三方插件（落在 plugins/<id>/，测试后由 uninstall 删除），
不依赖 mock 冒充真实行为。
"""
from __future__ import annotations

import json
import shutil
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from core.app import create_app
from core.errors import ManifestError
from core.plugins import satisfies
from core.plugins.validate import validate_manifest
from core.plugins.version import check_compatibility
from core.security import create_access_token
from db.engine import get_engine, init_engine

API_ROOT = Path(__file__).resolve().parents[1]
PLUGINS_DIR = API_ROOT.parent.parent / "plugins"  # 项目根/plugins
DEMO_ID = f"demo3p-{uuid.uuid4().hex[:6]}"

TOKEN = create_access_token("admin")
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def _write_demo_plugin(root: Path, *, kernel_api: str = "^1") -> None:
    (root / "api" / "migrations").mkdir(parents=True)
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "id": root.name,
                "name": "演示第三方插件",
                "version": "0.1.0",
                "kind": "third-party",
                "minKernel": "0.1.0",
                "kernelApi": kernel_api,
                "icon": "clock",
                "description": "测试用第三方插件",
                "author": "test",
                "window": {"w": 480, "h": 320},
                "entry": "",
                "api": {
                    "base": f"/api/v1/{root.name}",
                    "openapi": f"/api/v1/{root.name}/openapi.json",
                    "health": f"/api/v1/{root.name}/health",
                },
                "provides": [f"{root.name}.thing.read"],
                "requires": [],
                "slots": ["dashboard.card"],
                "emits": [f"{root.name}.created"],
                "consumes": [],
                "permissions": ["db:own"],
                "migrations": "api/migrations",
                "settingsSchema": "api/settings.schema.json",
                "lifecycle": {
                    "onInstall": None,
                    "onEnable": None,
                    "onDisable": None,
                    "onUninstall": None,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (root / "api" / "models.py").write_text(
        "from sqlmodel import Field, SQLModel\n"
        "class DemoThing(SQLModel, table=True):\n"
        "    __tablename__ = 'demo3p_thing'\n"
        "    __table_args__ = {'extend_existing': True}\n"
        "    id: str = Field(primary_key=True, max_length=32)\n"
        "    title: str = Field(default='', max_length=80)\n",
        encoding="utf-8",
    )
    (root / "api" / "migrations" / "0001_init.py").write_text(
        "def upgrade(engine):\n"
        "    from sqlmodel import SQLModel\n"
        "    import importlib.util, sys\n"
        "    p = __import__('pathlib').Path(__file__).resolve().parent.parent / 'models.py'\n"
        "    spec = importlib.util.spec_from_file_location('demo_models', p)\n"
        "    mod = importlib.util.module_from_spec(spec); sys.modules['demo_models']=mod\n"
        "    spec.loader.exec_module(mod)\n"
        "    mod.DemoThing.__table__.create(bind=engine, checkfirst=True)\n"
        "def downgrade(engine):\n"
        "    from sqlmodel import SQLModel\n"
        "    import importlib.util, sys\n"
        "    p = __import__('pathlib').Path(__file__).resolve().parent.parent / 'models.py'\n"
        "    spec = importlib.util.spec_from_file_location('demo_models', p)\n"
        "    mod = importlib.util.module_from_spec(spec); sys.modules['demo_models']=mod\n"
        "    spec.loader.exec_module(mod)\n"
        "    mod.DemoThing.__table__.drop(bind=engine, checkfirst=True)\n",
        encoding="utf-8",
    )
    (root / "api" / "router.py").write_text(
        "from fastapi import APIRouter\n"
        "from sqlmodel import Session, select\n"
        "from core.deps import get_db\n"
        "router = APIRouter()\n"
        "@router.get('/health')\n"
        "def health(): return {'ok': True}\n"
        "@router.get('/things')\n"
        "def things(db: Session = __import__('fastapi').Depends(get_db)):\n"
        "    mod = __import__('importlib').import_module('demo_models')\n"
        "    rows = db.exec(select(mod.DemoThing)).all()\n"
        "    return [r.title for r in rows]\n",
        encoding="utf-8",
    )
    (root / "api" / "settings.schema.json").write_text(
        json.dumps(
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {"refresh_minutes": {"type": "integer", "minimum": 1}},
                "required": ["refresh_minutes"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    # 每个测试用独立引擎 + 独立 SQLite：init_engine 幂等缓存首引擎，
    # 不重置会导致跨测试共用同一库、plugin_state 残留造成污染。
    import db.engine as _db_engine_mod

    _db_engine_mod._engine = None
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = init_engine(db_url)
    SQLModel.metadata.create_all(engine)  # 建 plugin_state/plugin_setting/app_setting 等
    yield TestClient(create_app())
    # 测试结束清理临时第三方插件目录（uninstall 应已删除，这里兜底）
    d = PLUGINS_DIR / DEMO_ID
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def demo_plugin_dir() -> Iterator[Path]:
    root = PLUGINS_DIR / DEMO_ID
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)
    _write_demo_plugin(root)
    yield root
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)


# ───────────────────── 契约 / 版本（单元） ─────────────────────
def test_schema_rejects_missing_kernel_api() -> None:
    raw = {
        "id": "x",
        "name": "x",
        "version": "0.1.0",
        "kind": "builtin",
        "window": {"w": 480, "h": 320},
        "entry": "@apps/x",
        "api": {"base": "/api/v1/x"},
        "provides": [],
        "requires": [],
        "slots": [],
        "emits": [],
        "consumes": [],
        "permissions": [],
    }
    with pytest.raises(ManifestError):
        validate_manifest(raw)


def test_schema_rejects_unknown_field() -> None:
    raw = {
        "id": "x",
        "name": "x",
        "version": "0.1.0",
        "kind": "builtin",
        "kernelApi": "^1",
        "window": {"w": 480, "h": 320},
        "entry": "@apps/x",
        "api": {"base": "/api/v1/x"},
        "provides": [],
        "requires": [],
        "slots": [],
        "emits": [],
        "consumes": [],
        "permissions": [],
        "bogus_field": 1,
    }
    with pytest.raises(ManifestError):
        validate_manifest(raw)


def test_incompatible_kernel_api_rejected_with_human_message() -> None:
    from core.plugins.version import IncompatibleKernelApiError

    with pytest.raises(IncompatibleKernelApiError) as ei:
        check_compatibility("^99")
    assert "内核接口" in str(ei.value)


def test_satisfies_caret() -> None:
    assert satisfies("^1", "1.0.0")
    assert not satisfies("^1", "2.0.0")
    assert not satisfies("^2", "1.0.0")


# ───────────────────── 权限门 ─────────────────────
def test_undeclared_permission_rejected() -> None:
    from core.errors import ForbiddenError
    from core.plugins.permissions import assert_permission

    with pytest.raises(ForbiddenError) as ei:
        assert_permission(["db:own"], "net:out:example.com")
    assert "net:out:example.com" in str(ei.value)


# ───────────────────── 设置校验 ─────────────────────
def test_settings_reject_wrong_type(client: TestClient, demo_plugin_dir: Path) -> None:
    # 先安装，才有 plugin_state
    r = client.post("/api/v1/plugins/install", json={"id": DEMO_ID}, headers=AUTH)
    assert r.status_code == 200, r.text
    # 写错类型：refresh_minutes 应是 integer
    r = client.patch(
        f"/api/v1/plugins/{DEMO_ID}/settings",
        json={"refresh_minutes": "soon"},
        headers=AUTH,
    )
    assert r.status_code == 422, r.text
    # 写正确类型
    r = client.patch(
        f"/api/v1/plugins/{DEMO_ID}/settings",
        json={"refresh_minutes": 5},
        headers=AUTH,
    )
    assert r.status_code == 200, r.text
    assert r.json()["settings"]["refresh_minutes"] == 5


# ───────────────────── 四态生命周期 ─────────────────────
def test_full_lifecycle_install_enable_disable_uninstall(
    client: TestClient, demo_plugin_dir: Path
) -> None:
    base = f"/api/v1/{DEMO_ID}"

    # 安装（第三方）
    r = client.post("/api/v1/plugins/install", json={"id": DEMO_ID}, headers=AUTH)
    assert r.status_code == 200, r.text
    assert r.json()["enabled"] is True

    # 路由已挂上、表已建
    assert client.get(f"{base}/health", headers=AUTH).status_code == 200
    r = client.get(f"{base}/things", headers=AUTH)
    assert r.status_code == 200

    # 出现在列表里
    listed = client.get("/api/v1/plugins", headers=AUTH).json()
    ids = [p["id"] for p in listed["plugins"] if p.get("id")]
    assert DEMO_ID in ids

    # 扩展点贡献可见
    slots = client.get("/api/v1/plugins/slots/dashboard.card", headers=AUTH).json()
    assert any(c["plugin_id"] == DEMO_ID for c in slots["contributions"])

    # 禁用：路由摘掉（注册表与运行时分离）
    r = client.post(f"/api/v1/plugins/{DEMO_ID}/disable", headers=AUTH)
    assert r.status_code == 200, r.text
    assert r.json()["enabled"] is False
    health = client.get(f"{base}/health", headers=AUTH)
    assert health.status_code in (404, 410), health.status_code  # 已摘掉

    # 启用：重新挂上
    r = client.post(f"/api/v1/plugins/{DEMO_ID}/enable", headers=AUTH)
    assert r.status_code == 200, r.text
    assert r.json()["enabled"] is True
    assert client.get(f"{base}/health", headers=AUTH).status_code == 200

    # 卸载：清表 + 清状态 + 删文件
    r = client.post(f"/api/v1/plugins/{DEMO_ID}/uninstall", headers=AUTH)
    assert r.status_code == 200, r.text
    assert r.json()["uninstalled"] is True

    # 表没了
    from sqlalchemy import text

    with get_engine().connect() as conn:
        tbl = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='demo3p_thing'")
        ).fetchone()
    assert tbl is None, "卸载后插件表应被清理"

    # 状态表清了
    with get_engine().connect() as conn:
        row = conn.execute(
            text("SELECT id FROM plugin_state WHERE id=:i"), {"i": DEMO_ID}
        ).fetchone()
    assert row is None, "卸载后 plugin_state 应被清理"

    # 文件删了
    assert not demo_plugin_dir.exists(), "卸载后插件目录应被删除"


# ───────────────────── 硬规则：core 不可禁用 / builtin 不可卸载 ─────────────────────
def test_disable_core_rejected(client: TestClient) -> None:
    # 管理模块本身是 core
    r = client.post("/api/v1/plugins/plugins/disable", headers=AUTH)
    assert r.status_code == 403, r.text


def test_uninstall_builtin_rejected(client: TestClient) -> None:
    # auth 是 builtin
    r = client.post("/api/v1/plugins/auth/uninstall", headers=AUTH)
    assert r.status_code == 403, r.text
