"""插件自带迁移的执行器（总纲 §1.3 / 验收 #7）。

每个插件在自己的 api/migrations/ 下放 0001_init.py 等，文件必须导出
    def upgrade(engine) -> None
    def downgrade(engine) -> None
（用 SQLModel 的 metadata.create_all / drop_all 或原生 DDL 均可）。

★ 两处来源一视同仁：builtin 在 modules/<id>/api/migrations/，
  third-party 在 plugins/<id>/api/migrations/。
★ 已执行的迁移记录在 app_setting（key = migration.<插件id>.<版本>），
  重启/重跑不重复执行（只增不改）。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from sqlmodel import text


def _migration_dir(info: Any) -> Path:
    return info.directory / "api" / "migrations"


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
    """执行插件尚未执行过的迁移，返回本次执行的版本列表。"""
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
