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
    kind: str = Field(pattern=r"^(symptom|medication|appointment|lab)$")
    title: str = Field(min_length=1, max_length=200)
    occurred_at: datetime
    severity: int | None = Field(default=None, ge=1, le=5)
    note: str | None = None
    followup_needed: bool = False
    followup_due: date | None = None


class HealthRecordUpdate(BaseModel):
    kind: str | None = Field(default=None, pattern=r"^(symptom|medication|appointment|lab)$")
    title: str | None = Field(default=None, min_length=1, max_length=200)
    occurred_at: datetime | None = None
    severity: int | None = Field(default=None, ge=1, le=5)
    note: str | None = None
    followup_needed: bool | None = None
    followup_due: date | None = None


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
    """TX-O1-01 · 单模块健康四态条目（结构态只读目击）。"""

    id: str
    name: str | None = None
    kind: str | None = None
    status: str
    activated: bool = False
    api_health_declared: bool = False
    detail: str | None = None


class ModulesStatusOut(BaseModel):
    """TX-O1-01 · 坞模块健康总览（四态 + 汇总 + E3 reconcile 并表）。"""

    ok: bool = True
    count: int = 0
    modules: list[ModuleHealthOut] = []
    summary: dict[str, int] = {}
    reconcile: ReconcileDigestOut = ReconcileDigestOut()
