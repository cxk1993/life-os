"""push 插件出入参。"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SubscribeKeys(BaseModel):
    p256dh: str = Field(min_length=10, max_length=200)
    auth: str = Field(min_length=5, max_length=200)


class SubscribeIn(BaseModel):
    endpoint: str = Field(min_length=20, max_length=500)
    keys: SubscribeKeys
    user_agent: str | None = Field(default=None, max_length=200)


class SubscriptionOut(BaseModel):
    id: str
    endpoint_prefix: str
    user_agent: str | None
    active: bool
    last_sent_at: datetime | None
    last_status: int | None
    fail_count: int
    created_at: datetime


class SendIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(default="", max_length=2000)
    url: str = Field(default="/", max_length=500)
    tag: str = Field(default="lifeos", max_length=64)


class SendResultOut(BaseModel):
    ok: bool
    sent: int
    pruned: int = 0
    detail: str | None = None


class PushLogOut(BaseModel):
    id: str
    topic: str
    title: str
    body: str | None
    ok: bool
    detail: str | None
    sent_at: datetime


class PushHealthOut(BaseModel):
    ok: bool = True
    enabled: bool = False
    vapid_ready: bool = False
    pywebpush_installed: bool = False
    subscriptions_active: int = 0
