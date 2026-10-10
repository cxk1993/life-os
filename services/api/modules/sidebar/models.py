"""· 侧栏自定义条目（高度自定义）。

★ 表名 sidebar_item（id 前缀铁律）。
★ note/announcement 的正文走 node_ref（笔记树），不另起存储。
★ href 协议白名单：只许 http/https（安全红线）。
★ 索引幂等：Field(index=True) 自动索引二次注册撞名 →
  改显式 Index(..., extend_existing=True)，Field 不再 index=True。
"""
from __future__ import annotations

from sqlalchemy import Index
from sqlalchemy import Text as SAText
from sqlmodel import Field

from db.base import PkMixin, TimestampMixin

# type 枚举
TYPE_LINK = "link"
TYPE_NOTE = "note"
TYPE_ANNOUNCEMENT = "announcement"
TYPE_FRIEND = "friend-link"
TYPES = (TYPE_LINK, TYPE_NOTE, TYPE_ANNOUNCEMENT, TYPE_FRIEND)


class SidebarItem(PkMixin, TimestampMixin, table=True):
    __tablename__ = "sidebar_item"
    # Table 幂等；Field 不用 index=True（自动索引二次注册会 4F36E）
    __table_args__ = (
        Index("ix_sidebar_item_type", "type"),
        Index("ix_sidebar_item_group", "group"),
        {"extend_existing": True},
    )

    type: str = Field(max_length=20)
    label: str = Field(max_length=40)
    icon: str = Field(default="", max_length=80)
    abbr: str = Field(default="", max_length=4)
    href: str = Field(default="", max_length=500)
    target: str = Field(default="_blank", max_length=10)
    body: str = Field(default="", sa_column=SAText())  # 仅 note/announcement 且 node_ref 空时
    node_ref: str = Field(default="", max_length=300)
    description: str = Field(default="", max_length=120)
    group: str = Field(default="", max_length=40)
    sort: int = Field(default=0)
    enabled: bool = Field(default=True)
    pinned: bool = Field(default=False)
