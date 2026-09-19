"""docs 出入参定义。

★ 出参直接返回资源本身，不包 {code,data}。
★ 时间字段一律带时区 ISO8601（datetime 类型，pydantic 自动序列化）。
★ 树查询返回整棵子树（文件管理器语义）；/trash /revisions /search 用 cursor 分页。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DocsNodeOut(BaseModel):
    """节点输出（轻量列，不含正文——正文按需加载）。"""

    id: str
    parent_id: str | None = None
    kind: str
    name: str
    sort: int = 0
    meta_json: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


class DocsNodeDetailOut(DocsNodeOut):
    """节点 + 正文（GET /nodes/{id}）。"""

    format: str | None = None
    body: str | None = None


class DocsTreeNode(DocsNodeOut):
    """树节点（含 children，一次装配成整棵子树）。"""

    children: list[DocsTreeNode] = Field(default_factory=list)


class DocsNodeCreate(BaseModel):
    """新建节点（folder/doc）。"""

    parent_id: str | None = Field(default=None, description="父节点 id；NULL = 根")
    kind: str = Field(description="folder | doc")
    name: str = Field(max_length=200)
    meta_json: dict[str, Any] | None = None
    sort: int = 0


class DocsNodeUpdate(BaseModel):
    """改名 / 移动(parent_id) / 改 meta_json / 改 sort。"""

    parent_id: str | None = None
    name: str | None = Field(default=None, max_length=200)
    meta_json: dict[str, Any] | None = None
    sort: int | None = None


class DocsContentIn(BaseModel):
    """保存正文。"""

    format: str = Field(default="md", description="txt | md")
    body: str = Field(default="", description="正文")


class DocsListOut(BaseModel):
    """扁平列表（/trash /revisions /search 通用分页形状）。"""

    items: list[dict[str, Any]] = Field(default_factory=list)
    next_cursor: str | None = None


class DocsSearchHit(BaseModel):
    """检索命中项。"""

    id: str
    name: str
    kind: str = "doc"
    parent_id: str | None = None
    snippet: str | None = Field(default=None, description="命中片段（截断）")
    created_at: datetime
    updated_at: datetime
