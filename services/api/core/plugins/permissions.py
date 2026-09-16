"""声明式权限（总纲 §1.3 / 验收 D）。

插件在 manifest.permissions 里声明它能做什么：
    db:own         读写自己的表（默认就要有）
    db:read:<id>   只读别人的表（尽量避免，优先走 API）
    bridge:read    读本机 Obsidian 桥
    net:out:<host> 访问外网（写具体域名）
    fs:plugin      读写自己插件目录下的文件
    notify:send    发通知

跨插件读数据必须走对方公开 API，并在 requires 里声明。
本模块提供"内核侧"的权限判定：插件调用内核能力前，内核据此拦截。
"""
from __future__ import annotations

import re
from collections.abc import Iterable

from core.errors import ForbiddenError

# 已知权限模板（用于校验 manifest 是否声明了合法权限；契约里已用正则兜底）。
_KNOWN_PREFIXES = ("db:own", "db:read:", "bridge:read", "net:out:", "fs:plugin", "notify:send")


def is_valid_permission(perm: str) -> bool:
    if perm == "db:own":
        return True
    if perm.startswith("db:read:"):
        return bool(re.fullmatch(r"db:read:[a-z][a-z0-9-]*", perm))
    if perm == "bridge:read":
        return True
    if perm.startswith("net:out:"):
        return bool(re.fullmatch(r"net:out:[a-z0-9.-]+", perm))
    if perm == "fs:plugin":
        return True
    return perm == "notify:send"


def has_permission(granted: Iterable[str], required: str) -> bool:
    """已授权集合里是否包含 required（支持通配语义：db:read:* 等同可读全部）。"""
    granted_set = set(granted)
    if required in granted_set:
        return True
    if required.startswith("db:read:") and "db:read:*" in granted_set:
        return True
    return required.startswith("net:out:") and "net:out:*" in granted_set


def assert_permission(granted: Iterable[str], required: str) -> None:
    """未授权时抛 403，并明确告知缺哪个权限（人话，不许静默）。"""
    if not has_permission(granted, required):
        raise ForbiddenError(
            f"权限不足：本次操作需要 {required!r}，"
            "但插件未声明该权限（请在 manifest.permissions 里声明）。"
        )


def assert_requires(plugin_requires: Iterable[str], capability: str) -> None:
    """跨插件能力依赖校验：插件 A 想用 B 的 <id>.<noun>.<verb> 能力，必须在 requires 里声明。"""
    if capability not in set(plugin_requires):
        raise ForbiddenError(
            f"能力依赖缺失：调用 {capability!r} 前必须在 manifest.requires 里声明。"
            "跨插件数据只能走对方公开 API，不许直接 join 别人的表。"
        )
