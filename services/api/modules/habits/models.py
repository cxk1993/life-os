"""插件模型：习惯打卡。

★ 表名必须以插件 id 为前缀（habits_xxx），否则内核拒绝建表。
★ 时间列一律用 db.base.TimestampTZ（UTC 存储 + 往返保时区）。
★ 打卡日期（habit_log.date）是「日期」语义，用 SQLAlchemy 的 Date 存日历日，
  不用 datetime —— 跨时区 / 跨日边界由业务层用 Asia/Shanghai(+8) 计算本地日。
★ Mixin 里的字段只能用 sa_type=（用 sa_column= 会在多表继承时抛
  "Column object ... already assigned to Table"）。

表：
  habits_habit  习惯定义（名称 / 目标 / 频率规则 / 颜色 / 提醒 / 休息日 / 归档）
  habits_log    打卡记录（习惯 id / 本地日期 / 值 / 备注 / 是否休息日）
"""
from __future__ import annotations

from datetime import date as DateType

from sqlalchemy import Date
from sqlalchemy import Text as SAText
from sqlmodel import Field

from db.base import PkMixin, TimestampMixin

# 频率规则类型：每天 / 每周 N 次 / 自定义星期
RULE_DAILY = "daily"
RULE_WEEKLY = "weekly"
RULE_CUSTOM = "custom"


class Habit(PkMixin, TimestampMixin, table=True):
    """一个习惯。表名前缀 habits_。"""

    __tablename__ = "habits_habit"

    name: str = Field(max_length=120, index=True)
    # 目标描述（自由文本，如「23:30 前睡」「30 分钟」）
    target: str = Field(default="", max_length=200)
    # 频率规则，JSON 字符串：{"type":"daily"} | {"type":"weekly","times":3}
    #                        | {"type":"custom","days":[0,2,4]}（0=周一 … 6=周日）
    rule: str = Field(default='{"type":"daily"}', max_length=200)
    # 颜色只用设计令牌（如 var(--accent)），不许硬编码 # 值
    color: str = Field(default="var(--accent)", max_length=32)
    # 提醒时间（本地 HH:MM）；空串表示不提醒
    reminder_time: str = Field(default="", max_length=8)
    # 休息星期（CSV，0=周一…6=周日）：这些天不打卡也不破 streak
    rest_weekdays: str = Field(default="", max_length=32)
    # 软删：归档后仍在表里，历史可查
    archived: bool = Field(default=False, index=True)
    # 展示顺序
    sort: int = Field(default=0)


class HabitLog(PkMixin, TimestampMixin, table=True):
    """一次打卡 / 一次请假。表名前缀 habits_。"""

    __tablename__ = "habits_log"

    habit_id: str = Field(
        max_length=32, index=True, foreign_key="habits_habit.id"
    )
    # 「日期」语义：本地日历日，不是带时区时刻。
    # 字段名不能叫 date（会与 datetime.date 类型注解撞名，Pydantic 直接拒绝建模）。
    date: DateType = Field(sa_type=Date, index=True)
    # 实际值（时长 / 次数 / 任意文本）；普通打卡留空
    value: str = Field(default="", max_length=120)
    # 长文本备注：sa_type= 传类型本身（与 calendar 同款，sa_column 要 Column 实例）
    note: str | None = Field(default=None, sa_type=SAText)
    # 这天是请假 / 休息日（不算完成但也不破 streak）
    is_rest: bool = Field(default=False)
