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
    # ★ 来源身份：human（人建）| ai（AI/MCP 来路建）。见 models.py 同名字段说明。
    origin: str = "human"
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
    text: str | None = Field(
        default=None, max_length=500, description="待办正文（一句话说清要做什么，如「交高数第四周作业」）"
    )
    due_at: datetime | None = Field(
        default=None,
        description="截止时间，带时区 ISO8601（如 2026-09-29T23:59:00+08:00）。它决定提醒何时推：到点前 24h（学业类）/ 30min（日常）",
    )
    priority: str | None = Field(
        default=None, description="优先级，只填 high | medium | low 三者之一（影响排序与推送文案）"
    )
    recur_rule: str | None = Field(
        default=None,
        description="周期规则（如 daily / weekly / 每周一）。非周期任务留空；填了则完成时自动生成下一次实例",
    )
    tags: list[str] = Field(
        default_factory=list,
        description=(
            "标签列表，用于分类与筛选。支持层级写法（如 学业/高数）；"
            "用 GET /tags 可查现有标签。"
            "★ 经 MCP / AI 创建时**必填非空**（防 AI 忘记分类）；人从网页创建时可留空"
        ),
    )


class TodoUpdate(BaseModel):
    text: str | None = Field(
        default=None, max_length=500, description="改正文（不传=不改）"
    )
    done: bool | None = Field(
        default=None,
        description="勾完成/取消完成：true=标记完成（写 done_at）；false=取消完成并清空 done_at。不传=不改",
    )
    due_at: datetime | None = Field(
        default=None, description="改截止时间，带时区 ISO8601；传 null 可清空截止"
    )
    priority: str | None = Field(default=None, description="改优先级：high | medium | low")
    recur_rule: str | None = Field(default=None, description="改周期规则；传 null 可清空")
    tags: list[str] | None = Field(
        default=None, description="**整组替换**标签（不是追加）——要保留原标签请连原标签一起传"
    )
    sort: int | None = Field(default=None, description="同层手动排序权重，越小越靠前")


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

    path: str | None = Field(
        default=None, description="本机 markdown 文件路径（与 content 二选一）"
    )
    content: str | None = Field(
        default=None, description="直接给 markdown 文本（与 path 二选一）"
    )


class ImportOut(BaseModel):
    imported: int
    lines: int  # 文件里任务行（- [ ] / - [x]）总数
    items: list[TodoItemOut] = []


class ExportIn(BaseModel):
    status: str | None = Field(
        default=None, description="导出范围：done=只导已完成 · todo=只导未完成 · all=全部（默认）"
    )
    tag: str | None = Field(
        default=None, description="只导出带该标签的（层级匹配：'学业' 会同时命中 '学业/高数'）"
    )


class ExportOut(BaseModel):
    markdown: str


class TodoTagOut(BaseModel):
    """★ 标签汇总的一项（2026-09-28 · 主人「AI 要能一目了然地分类」）。

    为什么需要：此前 AI 只能靠 `GET /items?tag=x` **逐个试**标签名 ——
    等于让 AI 猜"这库里到底有哪些标签"。有了这份汇总，一次调用就能看清
    "有哪些分类、各压着多少条"，才知道该往哪儿看、该按什么分。
    """

    tag: str
    todo: int  # 未完成条数
    done: int  # 已完成条数（★ 不含归档 —— 与界面「已完成」栏同口径）
    archived: int = 0  # ★ 2026-10-02：已完成满 ARCHIVE_AFTER_DAYS 天、已归档的条数
    total: int
