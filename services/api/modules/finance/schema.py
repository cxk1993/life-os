"""理财出入参。

★ 出参直接返回资源本身，不要包 {code,data}。
★ 时间字段一律带时区 ISO8601（datetime 类型，pydantic 自动序列化）。
★ 金额用整数分（amount_cents）或 Decimal 字符串（amount），禁止浮点。
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

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

    direction: Literal["expense", "income"] = Field(description="expense=支出 · income=收入")
    amount_cents: int | None = Field(default=None, ge=1, description="金额，**单位是分**（1 元 = 100 分）")
    amount: str | None = Field(default=None, max_length=32, description="Decimal 字符串金额")
    category: str = Field(default="", max_length=64, description="分类（如「餐饮」「交通」「工资」）")
    account: str = Field(default="", max_length=64, description="账户（如「微信」「银行卡」「现金」）")
    occurred_at: datetime = Field(description="发生时间，**必须带时区** ISO8601（如 2026-09-28T12:00:00+08:00）")
    note: str | None = Field(default=None, max_length=2000, description="备注（可选）")


class FinanceEntryUpdate(BaseModel):
    """部分更新：字段省略则不动；金额同样二选一。"""

    direction: Literal["expense", "income"] | None = Field(
        default=None, description="expense=支出 · income=收入"
    )
    amount_cents: int | None = Field(
        default=None, ge=1, description="金额，**单位是分**（1 元 = 100 分）；与 `amount` 二选一，都填以它为准"
    )
    amount: str | None = Field(
        default=None, max_length=32, description="Decimal 字符串金额（如 12.34）；与 `amount_cents` 二选一"
    )
    category: str | None = Field(default=None, max_length=64, description="改分类")
    account: str | None = Field(default=None, max_length=64, description="改账户")
    occurred_at: datetime | None = Field(default=None, description="改发生时间（必须带时区）")
    note: str | None = Field(default=None, max_length=2000, description="改备注")


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


# ───────────────── T08B BeeCount 只读快照 ─────────────────
# 金额字段名与 ADR/字典一致（total_asset/cash/invest/debt），单位整数分。
# BeeCount MCP 读不到细分时保持 0，原始摘要在 meta。


class FinanceSnapshotOut(BaseModel):
    """一条每日快照（date 全局唯一）。"""

    id: str
    date: date
    total_asset: int = 0
    cash: int = 0
    invest: int = 0
    debt: int = 0
    meta: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class FinanceSnapshotListOut(BaseModel):
    """快照列表：date 倒序 + 分页字段。"""

    items: list[FinanceSnapshotOut] = []
    total: int = 0
    limit: int = 30
    offset: int = 0


class SnapshotSyncOut(BaseModel):
    """POST /snapshots/sync 响应。

    upstream: mock | mcp
    snapshot: 当日 upsert 后的快照（同日覆盖，不会翻倍）
    """

    ok: bool = True
    upstream: str
    snapshot: FinanceSnapshotOut | None = None


class BeeCountSourceOut(BaseModel):
    """GET /beecount/source：上游状态（**绝不返回 token**）。

    upstream     FINANCE_UPSTREAM：mock | mcp
    configured   mcp 模式下 base_url + token 是否齐全；mock 恒为 true
    write_enabled 本轮只读，恒为 false
    """

    upstream: str
    configured: bool
    base_url_configured: bool
    token_present: bool
    last_sync: datetime | None = None
    last_snapshot_date: date | None = None
    snapshot_count: int = 0
    write_enabled: bool = False
    read_tools: list[str] = []
    mcp_path: str = "/api/v1/mcp"
