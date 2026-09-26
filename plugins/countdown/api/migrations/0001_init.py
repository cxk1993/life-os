"""插件迁移 0001：建 CountdownItem 表。

★ 只增不改：已执行过的迁移文件不许再动，要改就加 0002。
★ models.py 必须**按文件路径**加载，不能写 `from .models import ...`：
  内核是按文件路径加载插件文件的（core/plugins/discover.py），
  相对导入会抛 ImportError: attempted relative import with no known parent package。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

_MODEL_MODULE = "countdown_models"


def _load_models() -> Any:
    """按路径加载 models.py。

    ★ 必须先看 sys.modules 缓存：内核挂载第三方插件时会**再次**按路径加载
      `api/router.py`，而 router 也会加载同一份 models.py。
      若此处无条件 `exec_module`，SQLModel 类会被定义两次 →
      `sqlalchemy.exc.InvalidRequestError: Table 'xxx_item' is already defined
      for this MetaData instance`（本席 2026-09-23 段三 e2e 实跑到）。
      —— 生成器 `create_plugin.py` 的迁移模板缺这道判空，属模板缺陷，
      已在交接区《AST-D 段二·续一》报备。
    """
    cached = sys.modules.get(_MODEL_MODULE)
    if cached is not None:
        return cached
    path = Path(__file__).resolve().parent.parent / "models.py"
    spec = importlib.util.spec_from_file_location(_MODEL_MODULE, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_MODEL_MODULE] = mod
    spec.loader.exec_module(mod)
    return mod


def upgrade(engine: Any) -> None:
    _load_models().CountdownItem.__table__.create(bind=engine, checkfirst=True)


def downgrade(engine: Any) -> None:
    _load_models().CountdownItem.__table__.drop(bind=engine, checkfirst=True)
