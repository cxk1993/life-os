"""理财出入参。

★ 出参直接返回资源本身，不要包 {code,data}。
★ 时间字段一律带时区 ISO8601（datetime 类型，pydantic 自动序列化）。
★ 金额用整数分（amount_cents）或 Decimal 字符串（amount），禁止浮点。
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class FinanceEntryOut(BaseModel):
    id: str
    amount_cents: int
    direction: Literal["expense", "income"]
    category: str = ""
    account: str = ""
    occurred_at: datetime
    note: str | None = None
    created_at: datetime
    updated_at: datetime


class FinanceListOut(BaseModel):
    """列表响应：资源数组 + limit/offset 分页。"""

    items: list[FinanceEntryOut] = []
    total: int = 0
    limit: int = 50
    offset: int = 0


class FinanceEntryCreate(BaseModel):
    """新建一条流水。

    金额二选一：
    - amount_cents：整数分（推荐）
    - amount：Decimal 字符串，如 "12.34"（服务端换算成分，最多两位小数）
    """

    direction: Literal["expense", "income"]
    amount_cents: int | None = Field(default=None, ge=1, description="金额（分）")
    amount: str | None = Field(default=None, max_length=32, description="Decimal 字符串金额")
    category: str = Field(default="", max_length=64)
    account: str = Field(default="", max_length=64)
    occurred_at: datetime  # 必须带时区
    note: str | None = Field(default=None, max_length=2000)


class FinanceEntryUpdate(BaseModel):
    """部分更新：字段省略则不动；金额同样二选一。"""

    direction: Literal["expense", "income"] | None = None
    amount_cents: int | None = Field(default=None, ge=1)
    amount: str | None = Field(default=None, max_length=32)
    category: str | None = Field(default=None, max_length=64)
    account: str | None = Field(default=None, max_length=64)
    occurred_at: datetime | None = None
    note: str | None = Field(default=None, max_length=2000)


class CategoryTotal(BaseModel):
    category: str
    expense_cents: int = 0
    income_cents: int = 0
    count: int = 0


class FinanceSummaryOut(BaseModel):
    """区间汇总：固定 schema，前端/测试可依赖字段名。"""

    date_from: datetime | None = None
    date_to: datetime | None = None
    expense_cents: int = 0
    income_cents: int = 0
    net_cents: int = 0
    count: int = 0
    by_category: list[CategoryTotal] = []
