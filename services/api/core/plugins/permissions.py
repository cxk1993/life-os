"""声明式权限（总纲 §1.3 / 验收 D）。

插件在 manifest.permissions 里声明它能做什么（★ **两种格式**）：

【字符串格式】细粒度声明（内核原生，推荐）：
    db:own         读写自己的表（默认就要有）
    db:read:<id>   只读别人的表（尽量避免，优先走 API）
    bridge:read    读本机 Obsidian 桥
    net:out:<host> 访问外网（写具体域名）
    fs:plugin      读写自己插件目录下的文件
    notify:send    发通知
    subprocess     ★ 允许创建子进程（2026-09-25 新增，pi-agent 需起 RPC 子进程）

【对象格式】粗粒度开关（contracts/plugin.schema.json 的"新格式"，**本模块负责归一化**）：
    {"filesystem": true, "network": true, "subprocess": true}
    → 归一化为 ["fs:plugin", "net:out:*", "subprocess"]（★ 见 _OBJECT_MAP）

★ 为什么两者并存：schema 早就写了对象格式（"新插件请用对象格式"），但内核一直只实现
  字符串格式 —— 两层口径不一致（astrbot 2026-09-25 时发现）。
  此处**补齐对象格式支持**（归一化到字符串，不新增第二套判定逻辑），**存量插件零影响**。

跨插件读数据必须走对方公开 API，并在 requires 里声明。
本模块提供"内核侧"的权限判定：插件调用内核能力前，内核据此拦截。
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from core.errors import ForbiddenError

# 已知权限模板（用于校验 manifest 是否声明了合法权限；契约里已用正则兜底）。
_KNOWN_PREFIXES = (
    "db:own", "db:read:", "bridge:read", "net:out:", "fs:plugin", "notify:send",
    "subprocess",  # ★ 2026-09-25 pi-agent 起 RPC 子进程所需
)

# ★ 对象格式 → 字符串格式的归一化映射（2026-09-25 补）
#   原则：**只做保守映射，绝不放大权限** ——
#     filesystem:true → fs:plugin（不是"任意 fs"，字符串格式里也没有更宽的）
#     network:true    → net:out:*（schema 原文即"允许发起网络请求"，不限域名，语义相符）
#     subprocess:true → subprocess（新增）
_OBJECT_MAP: dict[str, str] = {
    "filesystem": "fs:plugin",
    "network": "net:out:*",
    "subprocess": "subprocess",
}


def normalize_permissions(raw: Any) -> list[str]:
    """把 manifest.permissions **归一化成字符串列表**（兼容新旧两种格式）。

    ★ 2026-09-25：schema 的"新格式"是对象
      （{"filesystem": true, ...}），内核此前只认字符串 —— 两层口径不一致。
      本函数是**唯一归一化入口**：对象 → 字符串（保守映射），字符串 → 原样。

    契约：
      - 入参为 dict：只取值为 True 且键在 _OBJECT_MAP 里的项；未知键忽略（由
        schema/validate 层报错，这里不抛——保持"内核运行期最小校验"的分工）。
      - 入参为 list：逐项转 str（容忍 None 等脏值，过滤空串）。
      - 其它：返回 []。
    """
    if isinstance(raw, dict):
        out: list[str] = []
        for key, val in raw.items():
            if val is True and key in _OBJECT_MAP:
                out.append(_OBJECT_MAP[key])
        return out
    if isinstance(raw, list | tuple | set):
        return [str(x) for x in raw if x]
    return []


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
    if perm == "subprocess":  # ★ 2026-09-25 新增
        return True
    return perm == "notify:send"


def has_permission(granted: Iterable[str], required: str) -> bool:
    """已授权集合里是否包含 required（支持通配语义：db:read:* / net:out:* 等同全部）。

    ★ subprocess 走普通精确匹配（无通配语义）。
    """
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
