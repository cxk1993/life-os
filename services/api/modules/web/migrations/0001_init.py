"""插件迁移 0001：建 WebEntry 表。

★ 只增不改：已执行过的迁移文件不许再动，要改就加 0002。
★ models.py 必须**按文件路径**加载，不能写 `from .models import ...`：
  迁移脚本是被内核按文件路径加载的（core/plugins/migrations.py），
  相对导入会抛 ImportError: attempted relative import with no known parent package。
  （★ 注意：这条只约束**迁移文件**；内置插件的 router.py / models.py 走包导入，可以用相对导入。）
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

_MODEL_MODULE = "web_models"


def _load_models() -> Any:
    path = Path(__file__).resolve().parent.parent / "models.py"
    spec = importlib.util.spec_from_file_location(_MODEL_MODULE, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_MODEL_MODULE] = mod
    spec.loader.exec_module(mod)
    return mod


def upgrade(engine: Any) -> None:
    _load_models().WebEntry.__table__.create(bind=engine, checkfirst=True)


def downgrade(engine: Any) -> None:
    _load_models().WebEntry.__table__.drop(bind=engine, checkfirst=True)
