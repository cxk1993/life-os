"""插件模型：Web Push。

★ 表名前缀必须是插件 id：push_
★ 时间列一律用 db.base.TimestampTZ（UTC 存储 + 往返保时区）。
★ 本文件被内核按「包路径」加载（modules.push.models），
  同源导入一律用 `from modules.push.xxx import ...`，不要相对导入。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Text as SAText
from sqlmodel import Field, SQLModel

from db.base import PkMixin, TimestampMixin, TimestampTZ


class PushSubscription(PkMixin, TimestampMixin, SQLModel, table=True):
    """一个浏览器/设备的 push 订阅。endpoint 唯一：重复订阅只刷新 keys。"""

    __tablename__ = "push_subscription"

    endpoint: str = Field(max_length=500, unique=True, index=True)
    p256dh: str = Field(max_length=200)
    auth: str = Field(max_length=200)
    user_agent: str | None = Field(default=None, max_length=200)

    # 投递统计（排障用：浏览器返回 404/410 即订阅失效）
    last_sent_at: datetime | None = Field(default=None, sa_type=TimestampTZ)
    last_status: int | None = Field(default=None)
    fail_count: int = Field(default=0)
    active: bool = Field(default=True)


class PushLog(PkMixin, TimestampMixin, SQLModel, table=True):
    """推送投递日志（审计：谁在什么时候被推了什么）。"""

    __tablename__ = "push_log"

    topic: str = Field(max_length=100, index=True)
    title: str = Field(max_length=200)
    body: str | None = Field(sa_type=SAText, default=None)
    ok: bool = Field(default=True)
    detail: str | None = Field(default=None, max_length=500)
    sent_at: datetime = Field(sa_type=TimestampTZ, index=True)
