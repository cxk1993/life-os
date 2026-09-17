"""AI 编排出入参。

★ 出参直接返回资源本身，不要包 {code,data}。
★ 时间字段一律带时区 ISO8601（datetime 类型，pydantic 自动序列化）。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AgentOut(BaseModel):
    id: str
    name: str
    description: str = ""
    capabilities: list[str] = []
    load: int = 0
    enabled: bool = True
    callback_url: str | None = None
    last_seen: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    capabilities: list[str] = Field(default_factory=list)
    callback_url: str | None = Field(default=None, max_length=300)
    enabled: bool = True


class AgentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    capabilities: list[str] | None = None
    enabled: bool | None = None
    callback_url: str | None = Field(default=None, max_length=300)
    load: int | None = Field(default=None, ge=0)


class TaskOut(BaseModel):
    id: str
    title: str
    description: str = ""
    status: str = "draft"
    assignee: str | None = None
    priority: int = 3
    inputs: list[Any] = []
    outputs: list[Any] = []
    acceptance: list[Any] = []
    constraints: list[Any] = []
    payload: dict[str, Any] = {}
    result: str | None = None
    result_status: str | None = None
    mode: str | None = None
    callback_url: str | None = None
    dispatch_id: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    attempts: int = 0
    trace_id: str | None = None
    source: str = "manual"
    created_at: datetime
    updated_at: datetime


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    assignee: str | None = Field(default=None, max_length=64)
    priority: int = Field(default=3, ge=1, le=5)
    inputs: list[Any] = Field(default_factory=list)
    outputs: list[Any] = Field(default_factory=list)
    acceptance: list[Any] = Field(default_factory=list)
    constraints: list[Any] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)
    mode: str | None = Field(default=None, max_length=16)
    callback_url: str | None = Field(default=None, max_length=300)
    source: str = Field(default="manual", max_length=16)


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    assignee: str | None = Field(default=None, max_length=64)
    priority: int | None = Field(default=None, ge=1, le=5)
    status: str | None = Field(default=None, max_length=16)
    inputs: list[Any] | None = None
    outputs: list[Any] | None = None
    acceptance: list[Any] | None = None
    constraints: list[Any] | None = None
    payload: dict[str, Any] | None = None
    mode: str | None = Field(default=None, max_length=16)
    callback_url: str | None = Field(default=None, max_length=300)


class DispatchIn(BaseModel):
    """派发任务块。v0.1 离线记账，不真调外网。"""

    agent_id: str | None = Field(default=None, description="指定接收 agent；省略则只入队")
    mode: str = Field(default="poll", max_length=16, description="webhook | poll | mcp")


class DispatchOut(BaseModel):
    id: str
    task_id: str
    dispatch_id: str
    mode: str
    target: str = ""
    status: str = "pending"
    attempts: int = 0
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime
    task: TaskOut


class ReportIn(BaseModel):
    """子 agent 回报。v0.1 由前端/测试直接写入，不依赖外部 AI API。"""

    result: str = Field(default="", max_length=20000)
    result_status: str | None = Field(default=None, max_length=16)
    outputs: list[Any] | None = None


class SummaryOut(BaseModel):
    """编排概览（dashboard 卡片用）。"""

    tasks_total: int = 0
    draft: int = 0
    queued: int = 0
    running: int = 0
    done: int = 0
    failed: int = 0
    cancelled: int = 0
    agents_total: int = 0
    agents_enabled: int = 0
