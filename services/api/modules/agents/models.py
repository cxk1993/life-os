"""插件模型：AI 编排（任务块分发）。

★ 表名必须以插件 id 为前缀（agents_），否则内核拒绝建表。
★ 时间列一律用 db.base.TimestampTZ（UTC 存储 + 往返保时区）。
★ Mixin 里的字段只能用 sa_type=（用 sa_column= 会在多表继承时抛
  "Column object ... already assigned to Table"）。
★ 本文件只 import db.base（内核），不 import 其它插件——保持数据库隔离。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column, Index, Text
from sqlmodel import Field

from db.base import PkMixin, TimestampMixin, TimestampTZ

# 任务块状态机：draft → queued → running → (done | failed | cancelled)
# done 之后不可再改（只能新建）；failed 可重试回 queued。
TASK_STATUS = ("draft", "queued", "running", "done", "failed", "cancelled")
# 分发模式
# ★ 2026-09-25 新增 "pi" —— 由内嵌 Pi agent 真执行（不再只记账）。
#   语义：dispatch(mode="pi") → 调 /api/v1/pi-agent/chat（任务块独立会话）→ 结果写回 task.result。
DISPATCH_MODE = ("webhook", "poll", "mcp", "pi")


class AgentTask(PkMixin, TimestampMixin, table=True):
    """一个任务块（agent_task）。表名前缀 = agents_。"""

    __tablename__ = "agents_task"
    __table_args__ = (
        Index("ix_agents_task_status_assignee", "status", "assignee"),
    )

    title: str = Field(max_length=200)
    description: str = Field(default="", sa_column=Column(Text))

    status: str = Field(default="draft", max_length=16, index=True)

    assignee: str | None = Field(default=None, max_length=64, index=True)
    priority: int = Field(default=3)  # 1 最高，5 最低

    # 结构化任务块字段（对齐总纲 §3.4 回报模板）
    inputs: Any = Field(default_factory=list, sa_column=Column(JSON, nullable=True))
    outputs: Any = Field(default_factory=list, sa_column=Column(JSON, nullable=True))
    acceptance: Any = Field(default_factory=list, sa_column=Column(JSON, nullable=True))
    constraints: Any = Field(default_factory=list, sa_column=Column(JSON, nullable=True))
    payload: Any = Field(default_factory=dict, sa_column=Column(JSON, nullable=True))

    # 子 agent 回报（markdown 原文 + 解析出的软状态）
    result: str | None = Field(default=None, sa_column=Column(Text))
    result_status: str | None = Field(default=None, max_length=16)

    # 分发相关
    mode: str | None = Field(default=None, max_length=16)  # webhook | poll | mcp
    callback_url: str | None = Field(default=None, max_length=300)
    dispatch_id: str | None = Field(default=None, max_length=64, unique=True, index=True)

    started_at: datetime | None = Field(default=None, sa_type=TimestampTZ)
    finished_at: datetime | None = Field(default=None, sa_type=TimestampTZ)
    attempts: int = Field(default=0)
    trace_id: str | None = Field(default=None, max_length=64)

    source: str = Field(default="manual", max_length=16)  # manual | decompose | poll


class AgentAgent(PkMixin, TimestampMixin, table=True):
    """注册到编排器的 agent 定义（名称/描述/能力标签 + 启用状态 + 负载）。"""

    __tablename__ = "agents_agent"

    name: str = Field(max_length=120, index=True)
    description: str = Field(default="", sa_type=Text)
    capabilities: Any = Field(default_factory=list, sa_column=Column(JSON, nullable=True))
    load: int = Field(default=0)  # 当前负载（进行中任务数）
    enabled: bool = Field(default=True)
    callback_url: str | None = Field(default=None, max_length=300)
    last_seen: datetime | None = Field(default=None, sa_type=TimestampTZ)


class AgentDispatch(PkMixin, TimestampMixin, table=True):
    """一次任务块投递记录（幂等键 + 重试 + 审计）。"""

    __tablename__ = "agents_dispatch"
    __table_args__ = (
        Index("ix_agents_dispatch_task", "task_id"),
        Index("ix_agents_dispatch_status", "status"),
    )

    task_id: str = Field(max_length=32, index=True, foreign_key="agents_task.id")
    dispatch_id: str = Field(max_length=64, unique=True, index=True)  # 幂等键
    mode: str = Field(max_length=16)  # webhook | poll | mcp
    target: str = Field(default="", max_length=300)  # callback_url 或 "poll"/"mcp"
    status: str = Field(default="pending", max_length=16)  # pending | sent | failed | ack
    attempts: int = Field(default=0)
    last_error: str | None = Field(default=None, sa_column=Column(Text))
