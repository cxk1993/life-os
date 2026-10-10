"""健康插件出入参。时间带时区 ISO8601。"""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class HealthRecordOut(BaseModel):
    id: str
    kind: str
    title: str
    occurred_at: datetime
    severity: int | None = None
    note: str | None = None
    followup_needed: bool = False
    followup_due: date | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class HealthRecordCreate(BaseModel):
    kind: str = Field(
        pattern=r"^(symptom|medication|appointment|lab)$",
        description="记录类型：symptom=症状 · medication=用药 · appointment=复诊 · lab=体检。**乱填直接 422**",
    )
    title: str = Field(min_length=1, max_length=200, description="一句话标题（如「头痛」「复查血常规」）")
    occurred_at: datetime = Field(description="发生时间，**必须带时区** ISO8601")
    severity: int | None = Field(
        default=None, ge=1, le=5, description="严重程度 1（最轻）–5（最重）；症状类常用，其它可留空"
    )
    note: str | None = Field(default=None, description="备注（剂量 / 医生嘱咐 / 检验单号等）")
    followup_needed: bool = Field(
        default=False, description="**是否需要跟进** —— true 时经事件总线**自动联动待办**"
    )
    followup_due: date | None = Field(
        default=None, description="跟进截止日。⚠️ 这是**日历日**（YYYY-MM-DD），不是带时区时刻"
    )


class HealthRecordUpdate(BaseModel):
    kind: str | None = Field(
        default=None, pattern=r"^(symptom|medication|appointment|lab)$", description="改类型（同样受四值约束）"
    )
    title: str | None = Field(default=None, min_length=1, max_length=200, description="改标题")
    occurred_at: datetime | None = Field(default=None, description="改发生时间（带时区）")
    severity: int | None = Field(default=None, ge=1, le=5, description="改严重程度（1–5）")
    note: str | None = Field(default=None, description="改备注")
    followup_needed: bool | None = Field(
        default=None, description="改是否需要跟进；由 false 改 true 时同样会联动待办"
    )
    followup_due: date | None = Field(default=None, description="改跟进截止日（日历日）")


class FollowupRequestOut(BaseModel):
    ok: bool
    event_topic: str = "health.care.requested"
    idempotency_key: str
    record_id: str


class ReconcileOut(BaseModel):
    ok: bool
    event_topic: str = "health.care.requested"
    desired_count: int
    published_count: int
    error_count: int = 0
    mode: str = "desired-state-broadcast"
    scheduler_enabled: bool = False
    published: list[dict] = []
    errors: list[dict] = []


class ReconcileStatusOut(BaseModel):
    event_topic: str = "health.care.requested"
    desired_count: int
    scheduler_enabled: bool = False
    records: list[HealthRecordOut] = []


class ReconcileDigestOut(BaseModel):
    """E3 reconcile 摘要（并表用，不带记录清单）。"""

    event_topic: str = "health.care.requested"
    desired_count: int = 0
    scheduler_enabled: bool = False


class ModuleHealthOut(BaseModel):
    """· 单模块健康四态条目（结构态只读目击）。"""

    id: str
    name: str | None = None
    kind: str | None = None
    status: str
    activated: bool = False
    api_health_declared: bool = False
    detail: str | None = None


class ModulesStatusOut(BaseModel):
    """· 坞模块健康总览（四态 + 汇总 + E3 reconcile 并表）。"""

    ok: bool = True
    count: int = 0
    modules: list[ModuleHealthOut] = []
    summary: dict[str, int] = {}
    reconcile: ReconcileDigestOut = ReconcileDigestOut()
