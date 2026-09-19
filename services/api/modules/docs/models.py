"""插件模型：docs_node / docs_content / docs_revision（文档树内核）。

★ 表名必须带 docs_ 前缀（内核拒绝建无前缀表）。
★ 时间列一律 db.base.TimestampTZ（UTC 存储 + 往返保时区）。
★ Mixin 字段只能用 sa_type=（用 sa_column= 会在多表继承时抛
  "Column object ... already assigned to Table"）。

★★ 留白判据（T15 的灵魂）：
  本文件不出现任何「人格 / 日记」专有列。所有扩展属性走 docs_node.meta_json。
  将来要加任何新东西（人格标签、日记心情、评分、封面……）都不需要改表：
  要么塞 meta_json，要么由壳插件自己带字段。

正文为何另存一张表：
  树查询只碰轻量的 docs_node（避免一次拉回所有正文拖慢树渲染）；
  正文 / 版本按需加载。body 是模型自有字段，可用 sa_type=Text 或 sa_column=Text。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel

from db.base import PkMixin, SoftDeleteMixin, TimestampMixin, TimestampTZ, utcnow


class DocsNode(PkMixin, TimestampMixin, SoftDeleteMixin, table=True):
    """树节点（文件夹 / 文稿）。

    自关联层级不强制限制深度（文件管理器语义，可任意嵌套）；
    移动时只校验「不能把节点移进自己的子孙」（防环），不做深度上限。
    """

    __tablename__ = "docs_node"
    __table_args__ = {"extend_existing": True}

    parent_id: str | None = Field(
        default=None, index=True, description="自关联 FK docs_node.id；NULL = 根节点"
    )
    kind: str = Field(index=True, description="folder | doc")
    name: str = Field(max_length=200, index=True, description="文稿标题 / 文件夹名")
    sort: int = Field(default=0, description="同层排序权重，默认 0")
    meta_json: str | None = Field(
        default=None,
        description=(
            "★ 所有扩展属性放这（JSON 字符串）。"
            '例：{"tags":[...],"icon":"🌟","mood":"平静"}。空 → NULL'
        ),
    )


class DocsContent(SQLModel, table=True):
    """正文（与节点 1:1，另存一张表）。"""

    __tablename__ = "docs_content"
    __table_args__ = {"extend_existing": True}

    node_id: str = Field(primary_key=True, description="FK docs_node.id ON DELETE CASCADE")
    format: str = Field(default="md", max_length=8, description="txt | md（默认 md）")
    body: str = Field(
        default="",
        sa_column=Column(Text),
        description="正文（10 万字级别也放得下，SQLite TEXT ≤ 1GB）",
    )
    updated_at: datetime = Field(default_factory=utcnow, sa_type=TimestampTZ, nullable=False)


class DocsRevision(PkMixin, TimestampMixin, table=True):
    """版本历史：每次保存正文写一条快照；回退本身也新增一条（历史不丢）。"""

    __tablename__ = "docs_revision"
    __table_args__ = {"extend_existing": True}

    node_id: str = Field(index=True, description="FK docs_content.node_id")
    content: str = Field(
        default="",
        sa_column=Column(Text),
        description="保存时的正文快照",
    )
    format: str = Field(default="md", max_length=8, description="当时的 txt/md")
