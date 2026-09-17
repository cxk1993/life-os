"""插件模型：理财。

★ 表名必须以插件 id 为前缀（`finance_xxx`），否则内核拒绝建表。
★ 时间列一律用 `db.base.TimestampTZ`（UTC 存储 + 往返保时区）。
★ Mixin 里的字段只能用 sa_type=（用 sa_column= 会在多表继承时抛
  "Column object ... already assigned to Table"）。
"""
from __future__ import annotations

from sqlmodel import Field

from db.base import PkMixin, TimestampMixin


class FinanceItem(PkMixin, TimestampMixin, table=True):
    __tablename__ = "finance_item"

    title: str = Field(default="", max_length=120, index=True)
