"""声明基类与通用 Mixin（T04 · 步骤 2）。

所有表统一带：id（UUID 字符串）/ created_at / updated_at（UTC，带时区）。
软删插件可选用 SoftDeleteMixin；内核表不用软删。

★ 各插件建表规矩（照抄 docs/示例/calendar_event_示例.py）：
    class CalendarEvent(PkMixin, TimestampMixin, SQLModel, table=True):
        __tablename__ = "calendar_event"   # 表名 = 插件 id 前缀 + 名词
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, event
from sqlalchemy.orm import Session as SASession
from sqlalchemy.types import TypeDecorator
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    """统一取 UTC 当前时间（带时区）。禁止 datetime.utcnow()（naive）。"""
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator[datetime]):
    """UTC 时间列（SQLite 往返不丢时区，验收项：存取往返不乱时区）。

    - 写入：必须带时区；统一转成 UTC 后存储（SQLite 本身无时区概念）
    - 读出：自动补 UTC tzinfo
    - naive 输入**直接报错**：项目铁律"时间必须带时区"，静默按本地处理是雷区 #7
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, _dialect: Any) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError(
                f"时间必须带时区（ISO8601，如 2026-09-15T08:00:00+08:00），收到 naive：{value!r}"
            )
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, _dialect: Any) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC)


# 全项目统一的时间列类型：UTC 存储 + 往返保时区。
# ★ 这里绑的是**类**而不是实例（`UTCDateTime()`），原因有两条，缺一不可：
#   1. SQLModel 的 `Field(sa_type=...)` 类型标注是 `type[Any]`，传实例 mypy 会报 call-overload；
#   2. Mixin 场景下必须让 SQLModel **为每张表新建列**。若改成 `sa_column=Column(...)`，
#      同一个 Column 对象会被复制进每一张表，第二张表就抛
#      `ArgumentError: Column object 'created_at' already assigned to Table`（实测踩过）。
#   传类时 SQLAlchemy 会自行实例化，每列一个实例，两条都满足。
TimestampTZ = UTCDateTime

# SQLModel 自身就是声明基类（单一 metadata：SQLModel.metadata）。
# 迁移脚本统一写 `from db.base import Base` 再用 Base.metadata，读起来更眼熟。
Base = SQLModel


class PkMixin(SQLModel):
    """主键：32 位 UUID hex 字符串（契约：ULID 或 UUID 字符串）。"""

    id: str = Field(
        default_factory=lambda: uuid4().hex,
        primary_key=True,
        max_length=32,
        description="UUID hex，全局唯一",
    )


class TimestampMixin(SQLModel):
    """created_at / updated_at，一律 UTC（UTCDateTime：往返保时区）。"""

    created_at: datetime = Field(
        default_factory=utcnow,
        sa_type=TimestampTZ,
        nullable=False,
        index=True,
    )
    updated_at: datetime = Field(
        default_factory=utcnow,
        sa_type=TimestampTZ,
        nullable=False,
    )


class SoftDeleteMixin(SQLModel):
    """软删（可选）：deleted_at 非空即视为已删。业务查询要自带过滤条件。"""

    deleted_at: datetime | None = Field(
        default=None,
        sa_type=TimestampTZ,
        nullable=True,
    )


@event.listens_for(SASession, "before_flush")
def _bump_updated_at(session: SASession, _ctx: Any, _instances: Any) -> None:
    """任何 update 都自动刷新 updated_at（写业务代码的人不用记这件事）。"""
    now = utcnow()
    for obj in session.dirty:
        if isinstance(getattr(obj, "updated_at", None), datetime):
            obj.updated_at = now
