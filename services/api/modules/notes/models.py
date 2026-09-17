"""插件模型：笔记。

★ 表名必须以插件 id 为前缀（`notes_xxx`），否则内核拒绝建表。
★ 时间列一律用 `db.base.TimestampTZ`（UTC 存储 + 往返保时区）。
★ Mixin 里的字段只能用 sa_type=（用 sa_column= 会在多表继承时抛
  "Column object ... already assigned to Table"）。
"""
from __future__ import annotations

from sqlmodel import Field

from db.base import PkMixin, TimestampMixin


class NotesItem(PkMixin, TimestampMixin, table=True):
    __tablename__ = "notes_item"

    title: str = Field(default="", max_length=120, index=True)
