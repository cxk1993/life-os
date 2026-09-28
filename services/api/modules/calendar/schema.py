"""日程表出入参（带时区）。

★ 出参**不要**包一层 `{"code":0,"data":...}`。**直接返回资源本身。**
★ 时间字段一律带时区 ISO8601；数据库里存 UTC。
★ children 递归成对实现「嵌套色块」的树形输出。
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class EventOut(BaseModel):
    """单个事件（可含子事件树）。

    树形输出：顶层事件 children 里挂直接子块，子块不再往下钻（由 service 控制 MAX_DEPTH）。
    """

    id: str
    title: str
    color: str
    start_at: datetime  # 带时区 ISO8601
    end_at: datetime
    all_day: bool
    span_days: int
    source: str
    parent_id: str | None = None
    sort: int
    location: str | None = None
    note: str | None = None
    children: list[EventOut] = Field(default_factory=list)


class EventCreate(BaseModel):
    """新建事件。支持一次带 children[]（每个 child 也是完整 EventCreate，parent_id 自动覆盖）。"""

    title: str = Field(
        min_length=1, max_length=200, description="事件标题（如「高等数学」「与导师讨论」）"
    )
    start_at: datetime = Field(
        description="开始时间，**必须带时区** ISO8601（如 2026-09-29T14:00:00+08:00）；库内存 UTC。**提醒以它为准**"
    )
    end_at: datetime = Field(description="结束时间，带时区 ISO8601；必须晚于 start_at")
    color: str = Field(
        default="var(--accent)",
        description="色块颜色。可传设计令牌（如 var(--accent)）或 #rrggbb",
    )
    all_day: bool = Field(
        default=False, description="是否全天事件（true 则不显示具体时刻，按整天占位）"
    )
    parent_id: str | None = Field(
        default=None, description="父事件 id —— 传了就作为**子块嵌在父色块里**；顶层事件留空"
    )
    span_days: int = Field(
        default=1, description="横跨天数（≥1）。跨天空的色块靠它撑开；改时间时子块会被自动钳制"
    )
    source: str = Field(
        default="manual", description="来源标记。人工新建=manual；其它模块代建请填模块名，便于日后区分"
    )
    sort: int = Field(default=0, description="同层排序权重（越小越靠前）")
    location: str | None = Field(default=None, description="地点（可选）")
    note: str | None = Field(default=None, description="备注（可选）")
    children: list[EventCreate] = Field(
        default_factory=list,
        description="**一次带子块**（每个元素是完整的 EventCreate；其 parent_id 会被自动覆盖成新建的这条）",
    )


class EventUpdate(BaseModel):
    """改标题/颜色/时间/跨天等。返回受影响子块的钳制后坐标（体现在响应树里）。"""

    title: str | None = Field(default=None, max_length=200, description="改标题（不传=不改）")
    color: str | None = Field(default=None, description="改色块颜色")
    start_at: datetime | None = Field(
        default=None, description="改开始时间（带时区 ISO8601）；挪时间时**子块会被自动钳制到父块范围内**"
    )
    end_at: datetime | None = Field(default=None, description="改结束时间（带时区 ISO8601）")
    all_day: bool | None = Field(default=None, description="改全天/非全天")
    span_days: int | None = Field(default=None, description="改横跨天数")
    sort: int | None = Field(default=None, description="改同层排序权重")
    location: str | None = Field(default=None, description="改地点")
    note: str | None = Field(default=None, description="改备注")


class FreeSlotOut(BaseModel):
    """一天里的空闲时段（AI 编排 / 概览都用它）。"""

    start: datetime
    end: datetime
    hours: float
