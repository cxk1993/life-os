"""插件迁移 0001：health_record。

★ models 按文件路径加载，不可相对导入。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

_MODEL_MODULE = "health_models"


def _load_models() -> Any:
    # 全量 pytest / lifespan：create_app 可能已 import 包路径 models，
    # 再按文件路径 exec 会重复定义 Table。优先复用已加载模块。
    for key in ("modules.health.models", _MODEL_MODULE):
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
    _load_models().HealthRecord.__table__.create(bind=engine, checkfirst=True)


def downgrade(engine: Any) -> None:
    _load_models().HealthRecord.__table__.drop(bind=engine, checkfirst=True)
