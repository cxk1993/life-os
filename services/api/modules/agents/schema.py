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
    name: str = Field(
        min_length=1, max_length=120,
        description="agent 的名字 —— **任务的 assignee 存的就是它**，故应唯一且简短",
    )
    description: str = Field(default="", max_length=2000, description="这个 agent 是干什么的（人话描述）")
    capabilities: list[str] = Field(
        default_factory=list,
        description="能力清单（字符串数组，如 pi.chat.write）；派发时按它匹配",
    )
    callback_url: str | None = Field(
        default=None, max_length=300, description="webhook 回调地址（mode=webhook 时用）；留空=不回调"
    )
    enabled: bool = Field(default=True, description="是否启用：停用的 agent 不接新活（历史任务不受影响）")


class AgentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120, description="改名字（不传=不改）")
    description: str | None = Field(default=None, max_length=2000, description="改描述")
    capabilities: list[str] | None = Field(
        default=None,
        description="**整组替换**能力清单（不是追加）——要保留原来的，请连原来的一起传",
    )
    enabled: bool | None = Field(default=None, description="启用 / 停用")
    callback_url: str | None = Field(default=None, max_length=300, description="改 webhook 回调地址")
    load: int | None = Field(default=None, ge=0, description="当前负载（供编排参考；一般由调度方自报）")


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
    title: str = Field(min_length=1, max_length=200, description="任务标题（一句话说清要做什么）")
    description: str = Field(default="", max_length=5000, description="任务详述（交付说明 / 背景 / 边界）")
    assignee: str | None = Field(
        default=None, max_length=64,
        description="指定承接者：填 **agent 的 name**（不是 id）；留空=先入队不指派",
    )
    priority: int = Field(
        default=3, ge=1, le=5, description="优先级 **1 最高、5 最低**（默认 3）；列表按它升序排"
    )
    inputs: list[Any] = Field(default_factory=list, description="输入材料清单（任务块契约槽之一，结构自由）")
    outputs: list[Any] = Field(default_factory=list, description="期望产出清单（交付物定义）")
    acceptance: list[Any] = Field(default_factory=list, description="验收标准清单（怎样算干完）")
    constraints: list[Any] = Field(default_factory=list, description="约束条件清单（不许做什么 / 硬性边界）")
    payload: dict[str, Any] = Field(default_factory=dict, description="给执行体的原始参数（任意 JSON 对象）")
    mode: str | None = Field(
        default=None, max_length=16,
        description="执行方式：pi=**真执行**（调内嵌 Pi）· webhook · poll · mcp（后三者只记账，不真调外网）",
    )
    callback_url: str | None = Field(default=None, max_length=300, description="本条任务的回调地址（覆盖 agent 级设置）")
    source: str = Field(default="manual", max_length=16, description="来源标记（manual=人工建的；其它模块代建请填模块名）")


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200, description="改标题")
    description: str | None = Field(default=None, max_length=5000, description="改详述")
    assignee: str | None = Field(default=None, max_length=64, description="改承接者（填 agent 的 name）")
    priority: int | None = Field(default=None, ge=1, le=5, description="改优先级（1 最高、5 最低）")
    status: str | None = Field(
        default=None, max_length=16,
        description="手工推进状态：draft | queued | running | done | failed | cancelled。⚠️ 受状态机约束，非法迁移会被拒",
    )
    inputs: list[Any] | None = Field(default=None, description="**整组替换**输入材料清单")
    outputs: list[Any] | None = Field(default=None, description="**整组替换**期望产出清单")
    acceptance: list[Any] | None = Field(default=None, description="**整组替换**验收标准清单")
    constraints: list[Any] | None = Field(default=None, description="**整组替换**约束条件清单")
    payload: dict[str, Any] | None = Field(default=None, description="**整组替换**执行参数（不是合并）")
    mode: str | None = Field(default=None, max_length=16, description="改执行方式：pi | webhook | poll | mcp")
    callback_url: str | None = Field(default=None, max_length=300, description="改回调地址")


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

    result: str = Field(
        default="", max_length=20000, description="执行结果正文（人话总结或结构化文本，≤20000 字）"
    )
    result_status: str | None = Field(
        default=None, max_length=16, description='结果状态，常用 "ok" / "failed"（自由字符串，服务端不强校验）'
    )
    outputs: list[Any] | None = Field(
        default=None, description="产出物清单（**整组替换**；结构自由 — 文件路径 / 链接 / 摘要条目等）"
    )


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
