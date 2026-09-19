"""插件模型：能力目录（手动条目）。

★ 表名必须以插件 id 为前缀（`catalog_xxx`），否则内核拒绝建表。
★ 时间列一律用 `db.base.TimestampTZ`（UTC 存储 + 往返保时区）。
★ Mixin 里的字段只能用 sa_type=（用 sa_column= 会在多表继承时抛
  "Column object ... already assigned to Table"）。
★ capabilities 按项目惯例存 JSON 数组字符串（SQLite 无数组类型），
  配 caps_from_json / caps_to_json 辅助函数（对齐 web/todo 模块写法）。

★ 字段对齐 T19 的 CapabilityEntry（同一份数据形状的输入端/输出端）：
  手动条目 = source="manual" 的那批条目，字段与 CapabilityEntry 一致 + enabled 开关。
"""
from __future__ import annotations

import json
from typing import Any

from sqlmodel import Field

from db.base import PkMixin, TimestampMixin


def caps_from_json(raw: str | None) -> list[str]:
    """DB 里的 capabilities 字符串 → 列表（空/非法 → []）。"""
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(x) for x in parsed]
        return []
    except (ValueError, TypeError):
        return []


def caps_to_json(caps: list[str] | None) -> str | None:
    """能力列表 → JSON 数组字符串（空/None → None）。"""
    if not caps:
        return None
    return json.dumps([str(c) for c in caps], ensure_ascii=False)


class CatalogEntry(PkMixin, TimestampMixin, table=True):
    __tablename__ = "catalog_entry"

    # 对外形状（对齐 CapabilityEntry）
    name: str = Field(default="", max_length=120, index=True)
    kind: str = Field(default="web", max_length=20)
    url: str | None = Field(default=None, max_length=2000)
    endpoint: str | None = Field(default=None, max_length=2000)
    auth_ref: str | None = Field(default=None, max_length=200)
    capabilities: str | None = Field(default=None)  # JSON 数组字符串
    note: str | None = Field(default=None, max_length=1000)

    # 开关：enabled=false 的条目不出现（或标记不可用）
    enabled: bool = Field(default=True)

    # 手动条目在目录里的稳定 id 引用（CapabilityEntry.id，外部可引用）
    catalog_id: str = Field(default="", max_length=64, index=True)

    def to_capability(self) -> dict[str, Any]:
        """转成 T19 CapabilityEntry 同形状（source="manual"）。"""
        return {
            "id": self.catalog_id or self.id,
            "name": self.name,
            "kind": self.kind,
            "url": self.url,
            "endpoint": self.endpoint,
            "auth_ref": self.auth_ref,
            "capabilities": caps_from_json(self.capabilities),
            "enabled": self.enabled,
            "note": self.note,
            "source": "manual",
        }