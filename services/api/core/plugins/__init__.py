"""插件框架（T14 · 内核侧）。

对外暴露的入口：插件管理器、契约校验、版本判断、发现。
其余子模块（discover/validate/version/permissions/migrations/settings/lifecycle）
是内部实现，按职责拆开，便于单测与演进。
"""
from __future__ import annotations

from core.plugins.manager import PluginManager, get_plugin_manager
from core.plugins.validate import validate_manifest, validate_manifest_text
from core.plugins.version import KERNEL_API_VERSION, check_compatibility, satisfies

__all__ = [
    "PluginManager",
    "get_plugin_manager",
    "validate_manifest",
    "validate_manifest_text",
    "KERNEL_API_VERSION",
    "check_compatibility",
    "satisfies",
]
