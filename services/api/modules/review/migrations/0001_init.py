"""插件迁移 0001：建 review_daily / review_note 表。

★ 只增不改：已执行过的迁移文件不许再动，要改就加 0002。
★ models.py 必须**按文件路径**加载，不能写 `from .models import ...`。
★ 表名前缀 review_：review_daily（contracts/data-dictionary 已登记表名）；
  review_note 由本插件自建（批注，与机器日报分开）。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

_MODEL_MODULE = "review_models"


def _load_models() -> Any:
    path = Path(__file__).resolve().parent.parent / "models.py"
    spec = importlib.util.spec_from_file_location(_MODEL_MODULE, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_MODEL_MODULE] = mod
    spec.loader.exec_module(mod)
    return mod


def upgrade(engine: Any) -> None:
    models = _load_models()
    models.ReviewDaily.__table__.create(bind=engine, checkfirst=True)
    models.ReviewNote.__table__.create(bind=engine, checkfirst=True)


def downgrade(engine: Any) -> None:
    models = _load_models()
    models.ReviewNote.__table__.drop(bind=engine, checkfirst=True)
    models.ReviewDaily.__table__.drop(bind=engine, checkfirst=True)
