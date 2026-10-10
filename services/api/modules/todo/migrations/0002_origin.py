"""插件迁移 0002：todo_item 加 origin 列（来源身份）。

★ 只增不改：0001 已执行过的不许再动；加列只能新开 0002。
★ 存量数据补默认值 'human'（历史条目在加列前无所谓人建/AI 建，一律记 human，
  与 calendar_event.source 的默认值口径一致）。
★ 幂等：ADD COLUMN 在已加过的库上会抛 duplicate column，先探 PRAGMA 再决定。
★ models 按文件路径加载（同 0001，相对导入会炸）。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

_MODEL_MODULE = "todo_models_0002"


def _load_models() -> Any:
    # 全量 pytest / lifespan：create_app 可能已 import 包路径 models，
    # 再按文件路径 exec 会重复定义 Table。优先复用已加载模块。
    for key in ("modules.todo.models", _MODEL_MODULE):
        existing = sys.modules.get(key)
        if existing is not None:
            return existing
    path = Path(__file__).resolve().parent.parent / "models.py"
    spec = importlib.util.spec_from_file_location(_MODEL_MODULE, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_MODEL_MODULE] = mod
    spec.loader.exec_module(mod)
    return mod


def _columns(conn: Any, table: str) -> set[str]:
    rows = conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
    return {r[1] for r in rows}


def upgrade(engine: Any) -> None:
    _load_models()
    with engine.begin() as conn:
        exists = conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='todo_item'"
        ).fetchone()
        if not exists:
            # 全新库：表由 create_all 建，models 里已含 origin 列 ⇒ 无需 ALTER。
            return
        if "origin" in _columns(conn, "todo_item"):
            return  # 幂等：列已存在
        conn.exec_driver_sql(
            "ALTER TABLE todo_item ADD COLUMN origin VARCHAR(8) NOT NULL DEFAULT 'human'"
        )
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_todo_item_origin ON todo_item (origin)")


def downgrade(engine: Any) -> None:
    # SQLite 3.35+ 支持 DROP COLUMN；更老版本会报错——回滚失败可接受（数据不丢）。
    with engine.begin() as conn:
        exists = conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='todo_item'"
        ).fetchone()
        if not exists or "origin" not in _columns(conn, "todo_item"):
            return
        conn.exec_driver_sql("DROP INDEX IF EXISTS ix_todo_item_origin")
        conn.exec_driver_sql("ALTER TABLE todo_item DROP COLUMN origin")
