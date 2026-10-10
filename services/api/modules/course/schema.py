"""course 出入参定义。

★ 出参直接返回资源本身，不要包 {code,data}。
★ 时间字段一律带时区 ISO8601（datetime 类型，pydantic 自动序列化）。
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CourseOut(BaseModel):
    id: str
    name: str
    teacher: str | None = None
    location: str | None = None
    weekday: int = 0
    start_section: int | None = None
    end_section: int | None = None
    start_time: str | None = None
    end_time: str | None = None
    weeks: str | None = None
    term_start: str | None = None
    note: str | None = None
    enabled: bool = True
    sort: int = 0
    created_at: datetime
    updated_at: datetime


class CourseListOut(BaseModel):
    items: list[CourseOut] = []


class CourseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100, description="课名（如「高等数学」）")
    teacher: str | None = Field(default=None, max_length=50, description="任课教师（可选）")
    location: str | None = Field(default=None, max_length=100, description="上课地点（可选，如「中心校区理综楼 305」）")
    weekday: int = Field(default=0, ge=0, le=6, description="**0=周一 … 6=周日**（注意不是 0=周日）")
    start_section: int | None = Field(default=None, ge=1, le=20, description="起始节次（第几节开始，1–20）")
    end_section: int | None = Field(default=None, ge=1, le=20, description="结束节次（第几节结束，1–20）")
    start_time: str | None = Field(default=None, max_length=5, description='开始时刻 "HH:MM"（与节次二选一或并存）')
    end_time: str | None = Field(default=None, max_length=5, description='结束时刻 "HH:MM"')
    weeks: str | None = Field(
        default=None, max_length=200,
        description="周次范围（如 1-16 或 1-8,10-16）—— 决定这一周是否要上课",
    )
    term_start: str | None = Field(default=None, max_length=10, description="开学日 YYYY-MM-DD（算周次用；留空则用系统设置）")
    note: str | None = Field(default=None, max_length=500, description="备注")
    enabled: bool = Field(default=True, description="是否启用（停用后不排进课表、也不提醒）")
    sort: int = Field(default=0, description="排序权重（越小越靠前）")


class CourseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100, description="改课名")
    teacher: str | None = Field(default=None, max_length=50, description="改教师")
    location: str | None = Field(default=None, max_length=100, description="改地点")
    weekday: int | None = Field(default=None, ge=0, le=6, description="改星期（**0=周一 … 6=周日**）")
    start_section: int | None = Field(default=None, ge=1, le=20, description="改起始节次")
    end_section: int | None = Field(default=None, ge=1, le=20, description="改结束节次")
    start_time: str | None = Field(default=None, max_length=5, description='改开始时刻 "HH:MM"')
    end_time: str | None = Field(default=None, max_length=5, description='改结束时刻 "HH:MM"')
    weeks: str | None = Field(default=None, max_length=200, description="改周次范围（如 1-16）")
    term_start: str | None = Field(default=None, max_length=10, description="改开学日（YYYY-MM-DD）")
    note: str | None = Field(default=None, max_length=500, description="改备注")
    enabled: bool | None = Field(default=None, description="启用 / 停用")
    sort: int | None = Field(default=None, description="改排序权重")


class WeekGridOut(BaseModel):
    """周网格视图（前端直接渲染）。

    days 长度恒为 7（周一…周日），每格该天要上的课按节次（无节次按时间）升序。
    sections 为网格纵轴的完整节次列表（主人「节次做成纵轴」）。
    """

    days: list["DayColumn"] = []
    term_start: str | None = None
    term_week: int | None = None  # 当前是第几教学周（无 term_start 时为空）
    sections: list[int] = []  # 网格纵轴节次（如 [1..12]）
    today_weekday: int = 0  # 今天星期几（0=周一），前端高亮列用


class DayColumn(BaseModel):
    weekday: int
    label: str
    items: list[CourseOut] = []


class TermSettingsOut(BaseModel):
    """学期设置（存 plugin_setting，复用内核插件设置机制）。"""

    term_start: str | None = None


class TermSettingsIn(BaseModel):
    term_start: str | None = Field(default=None, max_length=10, description="YYYY-MM-DD")
