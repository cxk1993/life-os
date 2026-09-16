"""日程表出入参（带时区）。

★ 出参**不要**包一层 `{"code":0,"data":...}`。**直接返回资源本身。**
★ 时间字段一律带时区 ISO8601；数据库里存 UTC。
★ children 递归成对实现「嵌套色块」的树形输出。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

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
    parent_id: Optional[str] = None
    sort: int
    location: Optional[str] = None
    note: Optional[str] = None
    children: list["EventOut"] = Field(default_factory=list)


class EventCreate(BaseModel):
    """新建事件。支持一次带 children[]（每个 child 也是完整 EventCreate，parent_id 自动覆盖）。"""

    title: str = Field(min_length=1, max_length=200)
    start_at: datetime
    end_at: datetime
    color: str = "var(--accent)"
    all_day: bool = False
    parent_id: Optional[str] = None
    span_days: int = 1
    source: str = "manual"
    sort: int = 0
    location: Optional[str] = None
    note: Optional[str] = None
    children: list["EventCreate"] = Field(default_factory=list)


class EventUpdate(BaseModel):
    """改标题/颜色/时间/跨天等。返回受影响子块的钳制后坐标（体现在响应树里）。"""

    title: Optional[str] = Field(default=None, max_length=200)
    color: Optional[str] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    all_day: Optional[bool] = None
    span_days: Optional[int] = None
    sort: Optional[int] = None
    location: Optional[str] = None
    note: Optional[str] = None


class FreeSlotOut(BaseModel):
    """一天里的空闲时段（AI 编排 / 概览都用它）。"""

    start: datetime
    end: datetime
    hours: float
