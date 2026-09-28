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
    name: str = Field(
        min_length=1, max_length=120, description="习惯名（如「喝水」「跑步」「背单词」）"
    )
    target: str = Field(
        default="", max_length=200, description="目标描述（自由文本，如「每天 2000ml」「每周 3 次」）"
    )
    rule: Rule = Field(
        default_factory=Rule, description="频率规则（缺省=每天）；它决定哪天该打卡"
    )
    color: str = Field(default="var(--accent)", max_length=32, description="卡片颜色")
    reminder_time: str = Field(
        default="", max_length=8, description='提醒时刻 "HH:MM"（24 小时制）；留空=不提醒'
    )
    rest_weekdays: list[int] = Field(
        default_factory=list,
        description="**休息日**（0=周一 … 6=周日）：这些天不用打卡，也**不算断签**（streak 不受影响）",
    )
    sort: int = Field(default=0, description="排序权重（越小越靠前）")


class HabitUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120, description="改习惯名")
    target: str | None = Field(default=None, max_length=200, description="改目标描述")
    rule: Rule | None = Field(default=None, description="**整组替换**频率规则（不是合并）")
    color: str | None = Field(default=None, max_length=32, description="改卡片颜色")
    reminder_time: str | None = Field(default=None, max_length=8, description='改提醒时刻 "HH:MM"；传 "" 关闭提醒')
    rest_weekdays: list[int] | None = Field(
        default=None, description="**整组替换**休息日（不是追加）——要保留原来的请连原来的一起传"
    )
    archived: bool | None = Field(
        default=None, description="true=归档（软隐藏，历史打卡仍在）· false=取消归档"
    )
    sort: int | None = Field(default=None, description="改排序权重")


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

    date: DateType | None = Field(
        default=None,
        description="打卡的**日历日**（YYYY-MM-DD，本地时区）。省略 = 今天；补打过去的日子请显式传",
    )
    value: str = Field(
        default="", max_length=120, description="当次打卡值（自由文本，如「30 分钟」「2000ml」）"
    )
    note: str | None = Field(default=None, max_length=2000, description="备注（可选）")
    is_rest: bool = Field(
        default=False, description="true=把这一天标记为**休息**（不计入完成，也不算断签）"
    )


class SummaryOut(BaseModel):
    """今日概览（dashboard 卡片用）。"""

    total: int = 0
    done: int = 0
    pending: int = 0
    rest: int = 0
    best_streak: int = 0
