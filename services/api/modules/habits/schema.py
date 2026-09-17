"""习惯打卡出入参。

★ 出参直接返回资源本身，不要包 {code,data}。
★ 打卡日期是「日历日」语义（YYYY-MM-DD 的 date），不是带时区时刻。
"""
from __future__ import annotations

from datetime import date as DateType
from datetime import datetime

from pydantic import BaseModel, Field


class Rule(BaseModel):
    """频率规则。daily=每天；weekly=每周 N 次；custom=只在指定星期打卡。"""

    type: str = Field(default="daily", description="daily | weekly | custom")
    times: int | None = Field(default=None, ge=1, le=7, description="weekly 时：每周次数")
    days: list[int] | None = Field(
        default=None, description="custom 时：打卡星期，0=周一 … 6=周日"
    )


class HabitOut(BaseModel):
    id: str
    name: str
    target: str = ""
    rule: Rule
    color: str = "var(--accent)"
    reminder_time: str = ""
    rest_weekdays: list[int] = []
    archived: bool = False
    sort: int = 0
    # 今日状态（列表/详情都带上，前端不用再算）
    today_status: str = "pending"  # done | pending | rest
    streak: int = 0
    created_at: datetime
    updated_at: datetime


class HabitCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    target: str = Field(default="", max_length=200)
    rule: Rule = Field(default_factory=Rule)
    color: str = Field(default="var(--accent)", max_length=32)
    reminder_time: str = Field(default="", max_length=8)
    rest_weekdays: list[int] = Field(default_factory=list)
    sort: int = 0


class HabitUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    target: str | None = Field(default=None, max_length=200)
    rule: Rule | None = None
    color: str | None = Field(default=None, max_length=32)
    reminder_time: str | None = Field(default=None, max_length=8)
    rest_weekdays: list[int] | None = None
    archived: bool | None = None
    sort: int | None = None


class LogOut(BaseModel):
    id: str
    habit_id: str
    date: DateType
    value: str = ""
    note: str | None = None
    is_rest: bool = False
    created_at: datetime


class CheckIn(BaseModel):
    """打卡。date 省略 = 今天（按 Asia/Shanghai）。"""

    date: DateType | None = None
    value: str = Field(default="", max_length=120)
    note: str | None = Field(default=None, max_length=2000)
    is_rest: bool = False


class SummaryOut(BaseModel):
    """今日概览（dashboard 卡片用）。"""

    total: int = 0
    done: int = 0
    pending: int = 0
    rest: int = 0
    best_streak: int = 0
