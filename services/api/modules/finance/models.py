"""插件模型：理财（流水账）。

★ 表名必须以插件 id 为前缀（`finance_xxx`），否则内核拒绝建表。
★ 时间列一律用 `db.base.TimestampTZ`（UTC 存储 + 往返保时区）。
★ Mixin 里的字段只能用 sa_type=（用 sa_column= 会在多表继承时抛
  "Column object ... already assigned to Table"）。

字段设计：
  amount_cents  金额，整数分（避免浮点；恒为正，方向由 direction 表达）
  direction     expense（支出） | income（收入）
  category      分类（自由文本，v0.1 不做独立分类表）
  account       账户（自由文本，如 现金 / 招行 / 支付宝）
  occurred_at   发生时间（UTC，带时区写入）
  note          备注（可空长文本）
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Text as SAText
from sqlmodel import Field

from db.base import PkMixin, TimestampMixin, TimestampTZ

DIR_EXPENSE = "expense"
DIR_INCOME = "income"
DIRECTIONS = (DIR_EXPENSE, DIR_INCOME)


class FinanceEntry(PkMixin, TimestampMixin, table=True):
    """一条流水。表名前缀 finance_。"""

    __tablename__ = "finance_entry"
    __table_args__ = {"extend_existing": True}

    # 整数分，恒 >= 0；符号语义交给 direction
    amount_cents: int = Field(ge=0)
    direction: str = Field(max_length=8, index=True)  # expense | income
    category: str = Field(default="", max_length=64, index=True)
    account: str = Field(default="", max_length=64, index=True)
    occurred_at: datetime = Field(sa_type=TimestampTZ, index=True)
    note: str | None = Field(default=None, sa_type=SAText)
