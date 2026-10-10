"""内核权限体系 · 两种格式归一化 + subprocess（2026-09-25 · 修与补）。

背景（astrbot 时发现的两层口径不一致）：
  - `contracts/plugin.schema.json` 写着「新插件请用**对象格式**」
    （{"filesystem": true, "network": true, "subprocess": true}）；
  - 而内核 `core/plugins/permissions.py` **只实现字符串格式**，
    `core/manifest.py` 的 `permissions: list[str]` 更会把对象格式**直接判非法**；
  - 且字符串格式里**根本没有 subprocess**（pi-agent 起 RPC 子进程所需）。

本文件固化修复后的契约：
  1. 两种格式**都合法**（字符串细粒度 / 对象粗开关）；
  2. 归一化是**唯一入口**（`normalize_permissions`），对象 → 字符串**保守映射**；
  3. 新增 `subprocess`；
  4. **存量字符串插件零影响**（回归断言）。
"""
from __future__ import annotations

import pytest

from core.errors import ForbiddenError
from core.manifest import Manifest
from core.plugins.permissions import (
    assert_permission,
    has_permission,
    is_valid_permission,
    normalize_permissions,
)

# ── 归一化 ──────────────────────────────────────────────────────


def test_string_format_passthrough():
    """★ 回归：存量字符串格式原样返回（29 个既有插件靠这条）。"""
    assert normalize_permissions(["db:own", "fs:plugin", "net:out:localhost"]) == [
        "db:own",
        "fs:plugin",
        "net:out:localhost",
    ]


def test_object_format_normalized():
    """★ 新格式（对象）→ 字符串，保守映射。"""
    assert normalize_permissions(
        {"filesystem": True, "network": True, "subprocess": True}
    ) == ["fs:plugin", "net:out:*", "subprocess"]


def test_object_format_false_ignored():
    """值为 False 的开关 = 未授权，不进集合。"""
    assert normalize_permissions({"filesystem": False, "network": True}) == ["net:out:*"]


def test_object_format_unknown_key_ignored():
    """未知键忽略（schema/validate 层负责报错，内核运行期不抛）。"""
    assert normalize_permissions({"weird": True}) == []


def test_degenerate_inputs():
    assert normalize_permissions(None) == []
    assert normalize_permissions("db:own") == []
    assert normalize_permissions([]) == []
    assert normalize_permissions({"subprocess": "yes"}) == []  # 非 True 不算


# ── subprocess（新增）─────────────────────────────────────────────


def test_subprocess_is_valid():
    assert is_valid_permission("subprocess") is True


def test_subprocess_exact_match():
    """subprocess 无通配语义：精确匹配才算授权。"""
    assert has_permission(["subprocess"], "subprocess") is True
    assert has_permission(["fs:plugin"], "subprocess") is False
    assert has_permission(["net:out:*"], "subprocess") is False


def test_subprocess_assert_raises_when_missing():
    with pytest.raises(ForbiddenError):
        assert_permission(["fs:plugin"], "subprocess")
    assert_permission(["subprocess"], "subprocess")  # 不抛


# ── 既有语义回归（别被这次改动带偏）────────────────────────────────


def test_existing_semantics_unchanged():
    assert is_valid_permission("db:own")
    assert is_valid_permission("db:read:calendar")
    assert is_valid_permission("net:out:api.example.com")
    assert is_valid_permission("bridge:read")
    assert is_valid_permission("fs:plugin")
    assert is_valid_permission("notify:send")
    assert not is_valid_permission("db:read:BAD_ID")
    assert not is_valid_permission("net:out:")  # 空域名非法


def test_net_wildcard_still_works():
    assert has_permission(["net:out:*"], "net:out:localhost")
    assert has_permission(["db:read:*"], "db:read:calendar")


# ── manifest 模型：两种格式都要"看得见"────────────────────────────


def test_manifest_accepts_string_permissions():
    m = Manifest(
        id="t1", name="T1", version="0.1.0", kind="third-party",
        api={"base": "/api/v1/t1"}, permissions=["db:own"],
    )
    assert m.permissions == ["db:own"]


def test_manifest_accepts_object_permissions():
    """★ 修复前：对象格式会被 pydantic 判非法（与 schema 口径打架）。"""
    m = Manifest(
        id="t2", name="T2", version="0.1.0", kind="third-party",
        api={"base": "/api/v1/t2"},
        permissions={"filesystem": True, "subprocess": True},
    )
    assert m.permissions == {"filesystem": True, "subprocess": True}
    assert normalize_permissions(m.permissions) == ["fs:plugin", "subprocess"]


def test_pi_agent_manifest_permissions_are_grantable():
    """★ 实战锚点：pi-agent 的 manifest 必须同时通过"合法"与"归一化"两关。"""
    import json
    from pathlib import Path

    manifest_path = (
        Path(__file__).resolve().parents[3] / "plugins" / "pi-agent" / "manifest.json"
    )
    if not manifest_path.is_file():
        pytest.skip("pi-agent 插件不在本工作区")
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    granted = normalize_permissions(raw.get("permissions"))
    assert "subprocess" in granted, "pi-agent 必须拿到 subprocess（起 RPC 子进程）"
    assert "fs:plugin" in granted
    for perm in granted:
        assert is_valid_permission(perm), f"非法权限：{perm}"
