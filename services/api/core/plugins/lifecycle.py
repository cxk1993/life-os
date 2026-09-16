"""生命周期钩子（总纲 §1.3 / 验收 #5）。

插件在 api/lifecycle.py 里可定义四个可选钩子：
    def on_install(db: Session) -> None
    def on_enable(db: Session) -> None
    def on_disable(db: Session) -> None
    def on_uninstall(db: Session) -> None

钩子是"尽力而为"：文件/函数不存在 = 静默跳过（不算错误）。
钩子内部抛异常 → 被 manager 捕获并写进 plugin_state.last_error，
不许拖垮整个安装/卸载流程。
"""
from __future__ import annotations

import importlib.util
import sys
import traceback
from typing import Any

_STAGES = ("on_install", "on_enable", "on_disable", "on_uninstall")

_STAGE_ATTR = {
    "install": "on_install",
    "enable": "on_enable",
    "disable": "on_disable",
    "uninstall": "on_uninstall",
}


def _load_lifecycle_module(info: Any) -> Any | None:
    path = info.directory / "api" / "lifecycle.py"
    if not path.is_file():
        return None
    name = f"plugin_lifecycle_{info.id}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:  # noqa: BLE001
        return None
    return mod


def run_lifecycle_hook(info: Any, stage: str, *, db: Any = None) -> str | None:
    """执行某阶段钩子。返回 None 表示成功，返回字符串表示捕获到的错误。"""
    if stage not in _STAGE_ATTR:
        raise ValueError(f"未知生命周期阶段：{stage}")
    mod = _load_lifecycle_module(info)
    if mod is None:
        return None
    fn = getattr(mod, _STAGE_ATTR[stage], None)
    if not callable(fn):
        return None
    try:
        if db is not None:
            fn(db=db)
        else:
            fn()
    except Exception:  # noqa: BLE001
        return traceback.format_exc()
    return None
