"""ADR-0003 · 插件生命周期可逆性回归测试（2026-10-03 hermes）。

对应改动四处，每处至少一条"修复前必红"的判据：

  L1 manage.enable() 逆序补偿 —— 失败不得留下 enabled=True 的中间态
  L2 manager.disable() 逆序     —— on_disable 执行时自己的路由必须还在
  L3 activator 目击落库          —— 激活失败要进 plugin_state.last_error
  L4 registry.mount() 孤儿防护   —— include_router 抛异常后不得残留路由

理论依据：arXiv:2608.25512 §3.1（revertible effects）与 Theorem 16
（逆必须按 effect 应用顺序的逆序施加）。
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Iterator

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from core.app import create_app
from core.deps import db_session
from core.plugins.discover import PluginInfo
from core.plugins.manager import get_plugin_manager
from core.registry import ModuleRegistry
from db.engine import get_engine, init_engine
from db.models.system import PluginState

API_ROOT = Path(__file__).resolve().parent.parent  # services/api/
PLUGINS_DIR = API_ROOT.parent.parent / "plugins"  # 项目根/plugins

BROKEN_ID = "zzbroken"
MIGFAIL_ID = "zzmigfail"

PLUGIN_JSON_BASE = {
    "name": "可逆性测试插件",
    "version": "0.1.0",
    "kind": "third-party",
    "minKernel": "0.1.0",
    "kernelApi": "^1",
    "icon": "clock",
    "description": "ADR-0003 回归用",
    "author": "test",
    "window": {"w": 320, "h": 200},
    "entry": "",
    "provides": [],
    "requires": [],
    "slots": [],
    "emits": [],
    "consumes": [],
    "permissions": ["db:own"],
    "settingsSchema": "api/settings.schema.json",
    "lifecycle": {
        "onInstall": None,
        "onEnable": None,
        "onDisable": None,
        "onUninstall": None,
    },
}


def _write_plugin(root: Path, *, router_src: str, migration_src: str | None = None) -> None:
    (root / "api").mkdir(parents=True, exist_ok=True)
    manifest = dict(PLUGIN_JSON_BASE)
    manifest["id"] = root.name
    manifest["api"] = {
        "base": f"/api/v1/{root.name}",
        "openapi": f"/api/v1/{root.name}/openapi.json",
        "health": f"/api/v1/{root.name}/health",
    }
    if migration_src is not None:
        manifest["migrations"] = "api/migrations"
        (root / "api" / "migrations").mkdir(parents=True, exist_ok=True)
        (root / "api" / "migrations" / "0001_init.py").write_text(
            migration_src, encoding="utf-8"
        )
    (root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )
    (root / "api" / "router.py").write_text(router_src, encoding="utf-8")
    (root / "api" / "settings.schema.json").write_text(
        json.dumps(
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {"refresh_minutes": {"type": "integer", "minimum": 1}},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _cleanup(*ids: str) -> None:
    for pid in ids:
        d = PLUGINS_DIR / pid
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def isolated_db(tmp_path: Path) -> Iterator[None]:
    import db.engine as _db_engine_mod

    _db_engine_mod._engine = None
    engine = init_engine(f"sqlite:///{tmp_path / 'rev.db'}")
    SQLModel.metadata.create_all(engine)
    yield
    _cleanup(BROKEN_ID, MIGFAIL_ID)


@pytest.fixture
def client(isolated_db: None) -> Iterator[TestClient]:
    yield TestClient(create_app())
    _cleanup(BROKEN_ID, MIGFAIL_ID)


def _mk_info(pid: str) -> PluginInfo:
    """从磁盘发现出的真实 PluginInfo（走 discover，字段最全）。"""
    from core.plugins.discover import discover_plugins

    for p in discover_plugins().plugins:
        if p.id == pid:
            return p
    raise AssertionError(f"插件未被发现：{pid}")


def _state(pid: str) -> PluginState | None:
    with db_session() as db:
        return db.get(PluginState, pid)


# ───────────────────── L1 · enable() 逆序补偿 ─────────────────────
def test_enable_failure_leaves_no_midstate(client: TestClient) -> None:
    """修复前必红：enable 失败后 plugin_state.enabled 是 True（半提交）。

    router.py 故意 import 一个不存在的模块 → load_plugin_router 抛错 →
    mount_plugin 失败。正确行为：状态回到「未启用」，且 last_error 有记录。
    """
    _cleanup(BROKEN_ID)
    _write_plugin(
        PLUGINS_DIR / BROKEN_ID,
        router_src="import this_module_does_not_exist_xyz  # noqa\n",
    )
    mgr = get_plugin_manager()
    reg = ModuleRegistry()
    reg.bind(FastAPI())

    with pytest.raises(Exception):
        mgr.enable(BROKEN_ID, reg)

    st = _state(BROKEN_ID)
    assert st is not None, "失败后应留下可诊断的状态行"
    assert st.enabled is False, (
        f"★ 半提交回归：失败后 enabled 应为 False，实际 {st.enabled}"
    )
    assert st.last_error, "失败原因应写入 last_error"
    assert BROKEN_ID not in reg.mounted(), "失败后不得残留挂载登记"


def test_enable_failure_does_not_drop_pre_existing_table(isolated_db: None) -> None:
    """迁移补偿必须只回滚**本次执行**的版本，不得全量 drop 历史表。

    场景：插件表已存在（模拟历史迁移已跑过），本次 enable 因路由加载失败
    而回滚。若实现误用全量 rollback_migrations，已存在的数据表会被删掉 ——
    这是比原故障更严重的二次破坏。
    """
    _cleanup(MIGFAIL_ID)
    _write_plugin(
        PLUGINS_DIR / MIGFAIL_ID,
        router_src="import this_module_does_not_exist_xyz  # noqa\n",
        migration_src=(
            "from sqlmodel import text\n"
            "def upgrade(engine):\n"
            "    with engine.begin() as c:\n"
            "        c.execute(text('CREATE TABLE IF NOT EXISTS zzmigfail_t (id TEXT)'))\n"
            "def downgrade(engine):\n"
            "    with engine.begin() as c:\n"
            "        c.execute(text('DROP TABLE IF EXISTS zzmigfail_t'))\n"
        ),
    )
    from sqlmodel import text

    engine = get_engine()
    # 先手工跑一次迁移，模拟「历史 enable 已建表」
    from core.plugins.migrations import run_migrations

    info = _mk_info(MIGFAIL_ID)
    run_migrations(engine, info)
    with engine.connect() as conn:
        assert conn.execute(
            text("SELECT name FROM sqlite_master WHERE name='zzmigfail_t'")
        ).fetchone(), "前置条件：表应先存在"

    mgr = get_plugin_manager()
    reg = ModuleRegistry()
    reg.bind(FastAPI())
    with pytest.raises(Exception):
        mgr.enable(MIGFAIL_ID, reg)

    # 本次 enable 没跑新迁移 → 差分空 → 不得 drop 已存在的表
    with engine.connect() as conn:
        still = conn.execute(
            text("SELECT name FROM sqlite_master WHERE name='zzmigfail_t'")
        ).fetchone()
    assert still is not None, (
        "★ 二次破坏回归：补偿不得回滚历史迁移（表被误删）"
    )


# ───────────────────── L2 · disable() 逆序 ─────────────────────
def test_disable_runs_hook_before_unmount(isolated_db: None) -> None:
    """修复前必红：on_disable 执行时自己的路由已 404（顺序反了）。

    做法：把 app 对象存进 core.plugins.lifecycle 的模块级变量，让插件的
    on_disable 钩子在运行时探测「自己的路由此刻是否还挂在 app 上」。
    """
    pid = "zzorder"
    probe = PLUGINS_DIR / pid / "probe.txt"
    _cleanup(pid)
    _write_plugin(
        PLUGINS_DIR / pid,
        router_src=(
            "from fastapi import APIRouter\n"
            "router = APIRouter()\n"
            "@router.get('/health')\n"
            "def health(): return {'ok': True}\n"
        ),
    )
    (PLUGINS_DIR / pid / "api" / "lifecycle.py").write_text(
        "from pathlib import Path\n"
        "\n"
        "def on_disable(db=None):\n"
        "    import core.plugins.lifecycle as lc\n"
        "    app = getattr(lc, '_REV_TEST_APP', None)\n"
        "    paths = [getattr(r, 'path', '') for r in (app.routes if app else [])]\n"
        "    present = any(p.startswith('/api/v1/zzorder') for p in paths)\n"
        "    out = Path(__file__).resolve().parent.parent / 'probe.txt'\n"
        "    out.write_text('route_present=%s' % present)\n",
        encoding="utf-8",
    )
    try:
        app = FastAPI()
        reg = ModuleRegistry()
        reg.bind(app)
        mgr = get_plugin_manager()
        mgr.enable(pid, reg)
        assert pid in reg.mounted(), "前置条件：应先挂载成功"

        # 暴露 app 给钩子探测
        import core.plugins.lifecycle as _lc

        setattr(_lc, "_REV_TEST_APP", app)
        try:
            mgr.disable(pid, reg)
        finally:
            setattr(_lc, "_REV_TEST_APP", None)

        assert pid not in reg.mounted(), "禁用后路由应被摘掉"
        assert probe.is_file(), "on_disable 应被执行"
        assert probe.read_text(encoding="utf-8").strip() == "route_present=True", (
            "★ 逆序回归：on_disable 执行时自己的路由必须还在（先钩子后摘路由）"
        )
    finally:
        _cleanup(pid)


# ───────────────────── L4 · registry.mount() 孤儿路由防护 ─────────────────────
def test_mount_failure_leaves_no_orphan_routes() -> None:
    """修复前必红：include_router 部分写入后抛错 → 路由残留且无法 unmount。

    用 monkeypatch 精确复现「已写入若干路由、随后抛异常」的中间态（真实场景：
    prefix 冲突、依赖注入签名错误等在逐条转换途中失败）。判据是 mount 失败后
    app.routes 与调用前**逐元素一致**，且不留挂载登记。
    """
    app = FastAPI()
    reg = ModuleRegistry()
    reg.bind(app)
    before_ids = [id(r) for r in app.routes]

    router = APIRouter()

    @router.get("/a")
    def _a():  # pragma: no cover
        return {"a": 1}

    @router.get("/b")
    def _b():  # pragma: no cover
        return {"b": 1}

    real_include = app.include_router

    def _partial_then_boom(r, **kwargs):  # type: ignore[no-untyped-def]
        real_include(r, **kwargs)  # 真实写入两条路由
        raise RuntimeError("boom after partial write")

    app.include_router = _partial_then_boom  # type: ignore[method-assign]
    try:
        with pytest.raises(RuntimeError, match="boom"):
            reg.mount("zzboom", router, prefix="/api/v1/zzboom")
    finally:
        app.include_router = real_include  # type: ignore[method-assign]

    after_ids = [id(r) for r in app.routes]
    assert after_ids == before_ids, (
        "★ 孤儿路由回归：mount 失败后 app.routes 必须与调用前逐元素一致"
    )
    assert "zzboom" not in reg.mounted(), "失败不得登记挂载"


# ───────────────────── L3 · 激活目击落库 ─────────────────────
def test_activator_persists_error_to_plugin_state(isolated_db: None) -> None:
    """修复前必红：_last_error 只在内存，plugin_state.last_error 不被写。"""
    from core.plugins.activator import PluginActivator

    pid = BROKEN_ID
    _cleanup(pid)
    _write_plugin(
        PLUGINS_DIR / pid,
        router_src="import this_module_does_not_exist_xyz  # noqa\n",
    )
    with db_session() as db:
        db.add(PluginState(id=pid, enabled=True))
        db.commit()

    reg = ModuleRegistry()
    reg.bind(FastAPI())
    act = PluginActivator(reg)
    # 走 app.py 的同一注入路径
    act.set_persist_hook(get_plugin_manager().note_activation_error)

    info = _mk_info(pid)
    with pytest.raises(Exception):
        act.activate(info)

    assert pid in act.last_error, "内存目击表应有记录"
    st = _state(pid)
    assert st is not None and st.last_error, (
        "★ 落库回归：激活失败必须写进 plugin_state.last_error（重启不丢）"
    )
    assert "this_module_does_not_exist_xyz" in (st.last_error or "")


def test_activator_persist_is_optional(isolated_db: None) -> None:
    """未注入通道时退化为纯内存（单测友好），不得抛错。"""
    from core.plugins.activator import PluginActivator

    reg = ModuleRegistry()
    reg.bind(FastAPI())
    act = PluginActivator(reg)
    act.set_persist_hook(None)
    # 直接调私有落库：无钩子时应静默返回
    act._persist("whatever", "boom")  # noqa: SLF001
