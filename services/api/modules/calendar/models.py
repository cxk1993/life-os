"""插件模型：日程表。

★ 表名必须以插件 id 为前缀（`calendar_event`），否则内核拒绝建表。
★ 时间列一律用 `db.base.TimestampTZ`（UTC 存储 + 往返保时区）。
★ Mixin 里的字段只能用 sa_type=（用 sa_column= 会在多表继承时抛
  "Column object ... already assigned to Table"）。
★ 本文件被内核按「包路径」加载（modules.calendar.models），
  同源导入一律用 `from modules.calendar.xxx import ...`，不要相对导入。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Text as SAText
from sqlmodel import Field, SQLModel

from db.base import PkMixin, TimestampMixin, TimestampTZ


class CalendarEvent(PkMixin, TimestampMixin, SQLModel, table=True):
    """日程事件。表名前缀必须是插件 id：calendar_"""

    __tablename__ = "calendar_event"

    title: str = Field(max_length=200)
    # 颜色只用设计令牌（如 var(--accent)）；前端按色系深浅派生子块色。
    color: str = Field(default="var(--accent)", max_length=32)

    # 时间一律 UTC 存储（TimestampTZ 保证往返保时区）
    start_at: datetime = Field(sa_type=TimestampTZ, index=True)
    end_at: datetime = Field(sa_type=TimestampTZ, index=True)

    all_day: bool = Field(default=False)

    # 自关联 = 色块嵌套色块；层级 ≤3 由 service 层保证（MAX_DEPTH）。
    parent_id: str | None = Field(
        default=None, foreign_key="calendar_event.id", index=True
    )

    sort: int = Field(default=0)
    # 跨自然天数（如周五 20:00 → 周六 02:00 跨 2 天）。查询侧不依赖它，仅用于展示。
    span_days: int = Field(default=1)

    # manual | obsidian | ai
    source: str = Field(default="manual", max_length=16, index=True)
    external_ref: str | None = Field(default=None, max_length=200)
    location: str | None = Field(default=None, max_length=200)
    # 长文本备注：用 sa_type=（类型本身），不用 sa_column=（要 Column 实例，
    # 且多表继承时会撞 "Column object already assigned to Table"）。
    note: str | None = Field(default=None, sa_type=SAText)
