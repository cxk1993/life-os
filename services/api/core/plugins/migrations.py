"""插件自带迁移的执行器（总纲 §1.3 / 验收 #7）。

每个插件在自己的 api/migrations/ 下放 0001_init.py 等，文件必须导出
    def upgrade(engine) -> None
    def downgrade(engine) -> None
（用 SQLModel 的 metadata.create_all / drop_all 或原生 DDL 均可）。

★ 两处来源一视同仁：builtin 在 modules/<id>/api/migrations/，
  third-party 在 plugins/<id>/api/migrations/。
★ 已执行的迁移记录在 app_setting（key = migration.<插件id>.<版本>），
  重启/重跑不重复执行（只增不改）。

★ ISSUE-006（2026-09-20）：实盘 12 个 builtin 插件的迁移全放在
  modules/<id>/migrations/（无 api/ 前缀），内核原只扫 api/migrations/
  ⇒ 一条都不会跑。现改为**双目录探测**（契约位 api/migrations/ 优先、
  历史位 migrations/ 兜底），并提供**启动对账** reconcile_migrations()
  + lifespan 工厂 make_startup_lifespan()：服务真正开始服务前按台账
  补跑缺失迁移。第三方插件维持 install() 触发不变。
"""
from __future__ import annotations

import importlib.util
import sys
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from sqlmodel import text

from core.logging import get_logger

log = get_logger("kernel.plugins.migrations")


def _migration_dir(info: Any) -> Path:
    """迁移目录双位置探测（ISSUE-006）。

    契约位 api/migrations/ 优先；历史位 migrations/ 兜底（实盘 builtin 全在此）。
    两处都存在时契约位获胜（写新迁移请放 api/migrations/）；
    都不存在时返回契约位，让 _discover 自然返回空。
    """
    api_dir = info.directory / "api" / "migrations"
    if api_dir.is_dir():
        return api_dir
    legacy_dir = info.directory / "migrations"
    if legacy_dir.is_dir():
        return legacy_dir
    return api_dir


def _discover(info: Any) -> list[tuple[str, Path]]:
    """[(version, path)]，按文件名序。version = 文件名（去 .py）。"""
    d = _migration_dir(info)
    if not d.is_dir():
        return []
    out: list[tuple[str, Path]] = []
    for p in sorted(d.glob("*.py")):
        if p.name.startswith("__"):
            continue
        out.append((p.stem, p))
    return out


def _load(path: Path, info: Any) -> Any:
    name = f"plugin_migration_{info.id}_{path.stem}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载迁移文件：{path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    for fn in ("upgrade", "downgrade"):
        if not callable(getattr(mod, fn, None)):
            raise RuntimeError(f"迁移文件 {path} 缺少 {fn}() 函数")
    return mod


def _record_key(plugin_id: str, version: str) -> str:
    return f"migration.{plugin_id}.{version}"


def _recorded(engine: Any, plugin_id: str) -> set[str]:
    with engine.connect() as conn:
        exists = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='app_setting'")
        ).fetchone()
        if not exists:
            return set()
        rows = conn.execute(
            text("SELECT key FROM app_setting WHERE key LIKE :pat"),
            {"pat": f"migration.{plugin_id}.%"},
        ).fetchall()
    return {r[0] for r in rows}


def _record(engine: Any, plugin_id: str, version: str) -> None:
    from db.base import utcnow

    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO app_setting (id, key, value_json, created_at, updated_at) "
                "VALUES (:id, :key, :v, :now, :now)"
            ),
            {
                "id": __import__("uuid").uuid4().hex,
                "key": _record_key(plugin_id, version),
                "v": f'"{utcnow().isoformat()}"',
                "now": utcnow().isoformat(),
            },
        )


def _unrecord(engine: Any, plugin_id: str, version: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM app_setting WHERE key = :key"),
            {"key": _record_key(plugin_id, version)},
        )


def run_migrations(engine: Any, info: Any) -> list[str]:
    """执行插件尚未执行过的迁移，返回本次执行的版本列表。

    ★ 新库首启时台账表可能不存在：先 ensure_record_table（ISSUE-006 同款），
      否则 _record INSERT app_setting 会直接 OperationalError。
    """
    ensure_record_table(engine)
    done = _recorded(engine, info.id)
    executed: list[str] = []
    for version, path in _discover(info):
        key = _record_key(info.id, version)
        if key in done:
            continue
        mod = _load(path, info)
        mod.upgrade(engine)
        _record(engine, info.id, version)
        executed.append(version)
    return executed


def rollback_migrations(engine: Any, info: Any) -> list[str]:
    """倒序回滚插件已记录的迁移（卸载时用）。"""
    done = _recorded(engine, info.id)
    rolled: list[str] = []
    for version, path in reversed(_discover(info)):
        key = _record_key(info.id, version)
        if key not in done:
            continue
        mod = _load(path, info)
        mod.downgrade(engine)
        _unrecord(engine, info.id, version)
        rolled.append(version)
    return rolled


def has_migrations(info: Any) -> bool:
    return len(_discover(info)) > 0


# ───────────────────────── ISSUE-006 · 启动对账 ─────────────────────────


def ensure_record_table(engine: Any) -> None:
    """确保迁移台账表 app_setting 存在（ISSUE-006）。

    新库首启（删库自启 / 灾备重建 / 换机迁移）时内核表可能尚未由 alembic
    建；没有台账就无法记录已执行版本，对账会每次重复执行。按 T04 的
    AppSetting 模型 checkfirst 补建——只 import 使用，不改动 db/ 任何文件。
    """
    from db.models.system import AppSetting

    # SQLModel 模型的 __table__ 在运行期才挂上，mypy 桩不识别（attr-defined）
    AppSetting.__table__.create(bind=engine, checkfirst=True)  # type: ignore[attr-defined]


def reconcile_migrations(
    engine: Any, modules: Sequence[tuple[str, Path]]
) -> dict[str, list[str]]:
    """启动对账：按 (插件id, 目录) 逐个补跑未执行的迁移（ISSUE-006）。

    run_migrations 本身幂等（台账只增不改），这里补的是「启动时机」——
    builtin 插件以前只有 third-party install 会触发迁移，新库首启全部
    建表即 500。任一插件迁移失败即抛错（fail fast，不许静默带病启动）。

    返回 {插件id: 本次执行的版本列表}（未执行任何迁移的插件值为 []）。
    """
    ensure_record_table(engine)
    result: dict[str, list[str]] = {}
    for plugin_id, directory in modules:
        info = SimpleNamespace(id=plugin_id, directory=directory)
        try:
            result[plugin_id] = run_migrations(engine, info)
        except Exception as exc:
            raise RuntimeError(
                f"插件「{plugin_id}」启动迁移对账失败：{exc}"
            ) from exc
    return result


def make_startup_lifespan(modules: Sequence[tuple[str, Path]]) -> Any:
    """为 create_app 生成 lifespan：服务开始服务前对账补跑各插件迁移。

    引擎经 core.deps 注入链获取（Session.get_bind()）——core 不 import db
    的分层约定不破。阻塞发生在 uvicorn lifespan 阶段，此时还未对外服务，
    正是「表必须先于请求存在」的正确时机。
    """

    @asynccontextmanager
    async def lifespan(_app: Any) -> AsyncIterator[None]:
        from core.deps import get_db

        with get_db() as session:
            engine = session.get_bind()
        executed = reconcile_migrations(engine, modules)
        ran = {pid: v for pid, v in executed.items() if v}
        if ran:
            total = sum(len(v) for v in ran.values())
            log.info(
                "插件迁移对账完成：本次补跑 %d 个插件共 %d 个版本",
                len(ran),
                total,
                extra={"plugins": {pid: v for pid, v in ran.items()}},
            )
        yield

    return lifespan
