"""插件迁移 0001：push_subscription / push_log 建表。

★ 只增不改；models 按文件路径加载（同 calendar 0001/0002 先例，相对导入会炸）。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

_MODEL_MODULE = "push_models_0001"


def _load_models() -> Any:
    for key in ("modules.push.models", _MODEL_MODULE):
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


def upgrade(engine: Any) -> None:
    m = _load_models()
    m.PushSubscription.__table__.create(bind=engine, checkfirst=True)
    m.PushLog.__table__.create(bind=engine, checkfirst=True)


def downgrade(engine: Any) -> None:
    m = _load_models()
    m.PushLog.__table__.drop(bind=engine, checkfirst=True)
    m.PushSubscription.__table__.drop(bind=engine, checkfirst=True)
