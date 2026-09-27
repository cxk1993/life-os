"""插件模型：course_item（课程表 · **一行 = 一门课的一个上课时段**）。

★ 表名必须以插件 id 为前缀（course_）。
★ 时间列一律用 db.base.TimestampTZ（UTC 存储 + 往返保时区）。
★ Mixin 里的字段只能用 sa_type=（用 sa_column= 会在多表继承时抛错）。

设计取舍（2026-09-27 · 主人令「日程待办里加一页课程表」）：
  不拆 `course` / `course_slot` 两张表 —— 主人点名的字段就是
  「课名 / 教师 / 地点 / 星期 / 节次 / 周次」，正好是一行。
  一门课一周上两次 = 两行（name 相同、weekday 不同），改其中一次
  不影响另一次；周网格视图**直接渲染、无需 join**。

字段：
  name          课名（如「高等数学」）
  teacher       教师
  location      地点（如「知新楼 B203」）
  weekday       星期几：**0=周一 … 6=周日**（与 Python date.weekday() 同序）
  start_section 起始节次（1 起；仅用于网格定位，可空）
  end_section   结束节次（含；可空）
  start_time    上课时间 HH:MM（★ 推送以此为准，不是节次）
  end_time      下课时间 HH:MM
  weeks         周次表达式（如 "1-16" / "1,3,5-16"；空 = 每周都上）
  term_start    该课适用的学期起始日（YYYY-MM-DD，用于把 weeks 换算成真实日期；可空）
  note          备注
  enabled       是否启用（临时停课置 false，不删数据）
  sort          手动排序权重
"""
from __future__ import annotations

from sqlmodel import Field

from db.base import PkMixin, TimestampMixin, TimestampTZ  # noqa: F401  (TimestampTZ 供后续扩展)

WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


class CourseItem(PkMixin, TimestampMixin, table=True):
    """一条课程时段。"""

    __tablename__ = "course_item"
    __table_args__ = {"extend_existing": True}

    name: str = Field(max_length=100, index=True)
    teacher: str | None = Field(default=None, max_length=50)
    location: str | None = Field(default=None, max_length=100)
    weekday: int = Field(default=0, index=True)  # 0=周一 … 6=周日
    start_section: int | None = Field(default=None)
    end_section: int | None = Field(default=None)
    start_time: str | None = Field(default=None, max_length=5)  # HH:MM
    end_time: str | None = Field(default=None, max_length=5)  # HH:MM
    weeks: str | None = Field(default=None, max_length=200)
    term_start: str | None = Field(default=None, max_length=10)  # YYYY-MM-DD
    note: str | None = Field(default=None, max_length=500)
    enabled: bool = Field(default=True, index=True)
    sort: int = Field(default=0)
