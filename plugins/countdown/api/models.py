"""插件模型：纪念日倒数（countdown）。

★ 表名以插件 id 为前缀（`countdown_item`），否则内核拒绝建表。
★ 时间列一律用 db.base 的 TimestampMixin（UTC 存储 + 往返保时区）；
  本插件的 target_date 是「日历日」语义（YYYY-MM-DD），与 habits 的打卡日期同源，
  **不存时刻、不带时区**——倒数日不存在"几点"，只存在"哪一天"。
★ Mixin 里的字段只能用 sa_type=（本文件未自定义 mixin 字段，遵守即可）。
"""

from __future__ import annotations

from datetime import date

from sqlmodel import Field

from db.base import PkMixin, TimestampMixin

#: kind 只有两种语义，且**必须在 API 层校验**（服务层见 service.KINDS）
KIND_COUNTDOWN = "countdown"  #: 一次性倒数日：目标日过去就是过去（days_left 可为负）
KIND_ANNIVERSARY = "anniversary"  #: 每年重复：目标日过后自动滚到明年（days_left 恒 >= 0）


class CountdownItem(PkMixin, TimestampMixin, table=True):
    """一条纪念日 / 倒数日。"""

    __tablename__ = "countdown_item"

    title: str = Field(default="", max_length=120, index=True)
    target_date: date = Field(default_factory=date.today, index=True)
    kind: str = Field(default=KIND_COUNTDOWN, max_length=16, index=True)
    note: str = Field(default="", max_length=500)
    color: str = Field(default="var(--accent)", max_length=40)
    #: 归档而非硬删：主人的纪念物是「记忆即资产」（灵感台账 #034 同一立场）
    archived: bool = Field(default=False, index=True)
