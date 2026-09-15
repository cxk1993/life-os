"""0001 · 内核五表：audit_log / idempotency_key / app_setting / plugin_state / plugin_setting

Revision ID: 0001
Revises:
Create Date: 2026-09-15

按模板包 2 的既定写法：用 SQLModel metadata 建表（避免手写 DDL 出错），
只建 KERNEL_TABLES 列出的五张，不碰将来插件自建的业务表。
迁移只增不改：本文件合并后不许再动，改结构 = 加 0002。
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KERNEL_TABLES = (
    "audit_log",
    "idempotency_key",
    "app_setting",
    "plugin_state",
    "plugin_setting",
)


def _kernel_tables():  # type: ignore[no-untyped-def]
    from db import models  # noqa: F401  导入即注册
    from db.base import Base

    missing = [t for t in KERNEL_TABLES if t not in Base.metadata.tables]
    if missing:
        raise RuntimeError(f"内核表模型缺失：{missing}")
    return [Base.metadata.tables[t] for t in KERNEL_TABLES]


def upgrade() -> None:
    from db.base import Base

    Base.metadata.create_all(bind=op.get_bind(), tables=_kernel_tables())


def downgrade() -> None:
    from db.base import Base

    Base.metadata.drop_all(bind=op.get_bind(), tables=list(reversed(_kernel_tables())))
