"""todo 出入参定义。

★ 出参直接返回资源本身，不要包 {code,data}。
★ 时间字段一律带时区 ISO8601（datetime 类型，pydantic 自动序列化）。
★ 入参 raw：一行原始 markdown，服务端用 todo_parser 解析。
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class TodoItemOut(BaseModel):
    id: str
    text: str
    done: bool
    done_at: datetime | None = None
    due_at: datetime | None = None
    priority: str | None = None  # high|medium|low
    recur_rule: str | None = None
    tags: list[str] = []
    source_path: str | None = None
    source_line: int | None = None
    sort: int = 0
    series_id: str | None = None
    instance_no: int = 0
    created_at: datetime
    updated_at: datetime


class TodoListOut(BaseModel):
    """列表响应：资源数组 + 游标分页（next_cursor 为空表示末页）。"""

    items: list[TodoItemOut] = []
    next_cursor: str | None = None


class TodoCreate(BaseModel):
    """新建一条。两种用法二选一：
    - raw：一行 Obsidian markdown，服务端解析（含快速添加语法糖）
    - 结构化字段：显式给 text / due_at / priority / recur_rule / tags
    """

    raw: str | None = Field(default=None, description="原始 markdown 行，服务端解析")
    text: str | None = Field(default=None, max_length=500)
    due_at: datetime | None = None  # 带时区 ISO8601
    priority: str | None = None  # high|medium|low
    recur_rule: str | None = None
    tags: list[str] = []


class TodoUpdate(BaseModel):
    text: str | None = Field(default=None, max_length=500)
    done: bool | None = None
    due_at: datetime | None = None
    priority: str | None = None
    recur_rule: str | None = None
    tags: list[str] | None = None
    sort: int | None = None


class ToggleOut(BaseModel):
    id: str
    done: bool
    done_at: datetime | None = None
    next_id: str | None = None  # 周期任务生成的下一个实例 id
    next_due_at: datetime | None = None  # 下一个实例的截止时间


class SummaryOut(BaseModel):
    today: int  # 今日待办（含逾期未完成的）
    overdue: int  # 逾期未完成
    week_done: int  # 本周完成


class ImportIn(BaseModel):
    """导入来源二选一：path（本机 notes 文件）或 content（直接给 markdown 文本）。"""

    path: str | None = None
    content: str | None = None


class ImportOut(BaseModel):
    imported: int
    lines: int  # 文件里任务行（- [ ] / - [x]）总数
    items: list[TodoItemOut] = []


class ExportIn(BaseModel):
    status: str | None = None  # done|todo|all
    tag: str | None = None


class ExportOut(BaseModel):
    markdown: str
