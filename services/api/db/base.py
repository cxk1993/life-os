"""声明基类与通用 Mixin（T04 · 步骤 2）。

所有表统一带：id（UUID 字符串）/ created_at / updated_at。
★ 时间口径（2026-09-28 主人令统一）：**库里存 UTC，读出转主人本地时区**。
  见 `TZDateTime` 的类注释。

★ 各插件建表规矩（照抄 docs/示例/calendar_event_示例.py）：
    class CalendarEvent(PkMixin, TimestampMixin, SQLModel, table=True):
        __tablename__ = "calendar_event"   # 表名 = 插件 id 前缀 + 名词
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import DateTime, event
from sqlalchemy.orm import Session as SASession
from sqlalchemy.types import TypeDecorator
from sqlmodel import Field, SQLModel

from core.config import get_settings


def utcnow() -> datetime:
    """统一取 UTC 当前时间（带时区）。禁止 datetime.utcnow()（naive）。"""
    return datetime.now(UTC)


class TZDateTime(TypeDecorator[datetime]):
    """时间列：**UTC 存储 + 本地时区读出**（★ 2026-09-28 · 主人令统一口径）。

    - 写入：必须带时区；统一转成 UTC 后存储（SQLite 本身无时区概念）
    - 读出：**转成主人本地时区**（settings.tz，默认 Asia/Shanghai）再交给上层
    - naive 输入**直接报错**：项目铁律"时间必须带时区"，静默按本地处理是雷区 #7

    ★ 为什么"读出即本地"必须放在**这里**，而不是各模块各转一次：
      全平台 **14 个模块 / 56 个输出时间字段**都要口径一致。若靠"每个模块记得转"，
      迟早会漏 —— 本次的起因正是"出参一律 UTC"这条约定在 calendar 上被单独推翻，
      暴露出 `today-summary` 拿 UTC 串切片当本地小时显示（**主人可见的错**）。
      钉在**唯一的存储原语**上 ⇒ 一处改、全体一致，且**未来新模块不可能忘**。

    ⚠️ 语义边界（很重要）：**库里存的仍是 UTC**（写入侧一个字没动），
      只是**进程内表示**变成本地。两者是**同一瞬间**，
      任何跨时区比较、排序、算术都不受影响（tz-aware 之间比较按瞬间比）。
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
        # 先补回 UTC（库里存的是 naive UTC 串），再转主人本地时区 —— 同一瞬间，换个表示。
        return value.replace(tzinfo=UTC).astimezone(ZoneInfo(get_settings().tz))


# 全项目统一的时间列类型：UTC 存储 + 往返保时区。
# ★ 这里绑的是**类**而不是实例（`UTCDateTime()`），原因有两条，缺一不可：
#   1. SQLModel 的 `Field(sa_type=...)` 类型标注是 `type[Any]`，传实例 mypy 会报 call-overload；
#   2. Mixin 场景下必须让 SQLModel **为每张表新建列**。若改成 `sa_column=Column(...)`，
#      同一个 Column 对象会被复制进每一张表，第二张表就抛
#      `ArgumentError: Column object 'created_at' already assigned to Table`（实测踩过）。
#   传类时 SQLAlchemy 会自行实例化，每列一个实例，两条都满足。
TimestampTZ = TZDateTime

# ⚠️ 旧名保留**仅为了不断外部引用**：它现在**不再是纯 UTC**（读出转本地）。
#    新代码请一律用 `TimestampTZ`；看到 `UTCDateTime` 请当成历史遗留。
UTCDateTime = TZDateTime


# ★ 索引创建全局幂等（令102/103）：测试中模型被反复注册（探针/lifespan reconcile/
# 多 fixture create_all），CREATE INDEX 二次执行撞名（ix_* already exists）。
# SQLite/PostgreSQL 均支持 CREATE INDEX IF NOT EXISTS——编译钩子统一兜底，对生产无害。
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.schema import CreateIndex as _CreateIndex


@compiles(_CreateIndex)
def _create_index_if_not_exists(element: Any, compiler: Any, **kw: Any) -> str:
    stmt = compiler.visit_create_index(element, **kw)
    if "IF NOT EXISTS" in stmt:
        return stmt
    return stmt.replace("CREATE INDEX", "CREATE INDEX IF NOT EXISTS", 1)


@compiles(_CreateIndex, "sqlite")
def _create_index_if_not_exists_sqlite(element: Any, compiler: Any, **kw: Any) -> str:
    stmt = compiler.visit_create_index(element, **kw)
    if "IF NOT EXISTS" in stmt:
        return stmt
    return stmt.replace("CREATE INDEX", "CREATE INDEX IF NOT EXISTS", 1)

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
    """created_at / updated_at（TZDateTime：UTC 存储、本地读出）。"""

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
