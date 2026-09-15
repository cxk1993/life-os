"""内核表模型（T04 · 步骤 3+4）。

★ 只建内核表（总纲 §1.5）：audit_log / idempotency_key / app_setting /
  plugin_state / plugin_setting。
★ 业务表（calendar_event / todo_item / habit ...）**不在**这里——
  由各插件自带模型与 migrations（见 docs/示例/calendar_event_示例.py）。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, UniqueConstraint
from sqlalchemy import Text as SAText
from sqlmodel import Field

from db.base import PkMixin, TimestampMixin, TimestampTZ, utcnow


class AuditLog(PkMixin, TimestampMixin, table=True):
    """audit_log · 谁动了什么（总纲 §1.6 审计底线）。"""

    __tablename__ = "audit_log"

    actor: str = Field(default="system", max_length=64, index=True)
    action: str = Field(max_length=64)
    target: str = Field(default="", max_length=200)
    payload_hash: str = Field(default="", max_length=64)
    at: datetime = Field(default_factory=utcnow, sa_type=TimestampTZ, index=True)
    ip: str = Field(default="", max_length=64)


class IdempotencyKey(PkMixin, TimestampMixin, table=True):
    """idempotency_key · 幂等记录（持久层就绪形态）。

    说明：T03 的幂等中间件目前是进程内缓存；本表是它落盘的既定形状——
    重启后依然能拒绝重放（总纲雷区 #8）。中间件何时切换到落盘由 T13 决定。
    """

    __tablename__ = "idempotency_key"

    key: str = Field(max_length=128, index=True, unique=True)
    method: str = Field(max_length=8)
    path: str = Field(max_length=300)
    request_hash: str = Field(max_length=64)
    response_status: int = Field(default=0)
    response_body: str = Field(default="", sa_column=Column(SAText))
    expires_at: datetime | None = Field(default=None, sa_type=TimestampTZ)


class AppSetting(PkMixin, TimestampMixin, table=True):
    """app_setting · 全局键值设置（value_json 是 JSON 字符串）。"""

    __tablename__ = "app_setting"

    key: str = Field(max_length=128, index=True, unique=True)
    value_json: str = Field(default="null", sa_column=Column(SAText))


class PluginState(TimestampMixin, table=True):
    """plugin_state · 插件注册状态（T14 用）。

    ★ id = 插件 id（不是随机 UUID）：注册表与运行时分离，是热插拔的前提。
    """

    __tablename__ = "plugin_state"

    id: str = Field(primary_key=True, max_length=64)  # = 插件 id
    version: str = Field(default="0.0.0", max_length=32)
    kind: str = Field(default="builtin", max_length=16)  # core|builtin|third-party
    enabled: bool = Field(default=True)
    installed_at: datetime = Field(default_factory=utcnow, sa_type=TimestampTZ)
    last_error: str | None = Field(default=None, sa_column=Column(SAText))
    granted_permissions: str = Field(default="[]", sa_column=Column(SAText))


class PluginSetting(PkMixin, TimestampMixin, table=True):
    """plugin_setting · 插件设置（按各插件 settingsSchema 校验后存）。"""

    __tablename__ = "plugin_setting"
    __table_args__ = (UniqueConstraint("plugin_id", "key", name="uq_plugin_setting"),)

    plugin_id: str = Field(max_length=64, index=True)
    key: str = Field(max_length=128)
    value_json: str = Field(default="null", sa_column=Column(SAText))
