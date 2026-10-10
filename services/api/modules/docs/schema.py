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
    name: str = Field(
        max_length=200, description="节点显示名（≤200 字）；同级可重名，但建议唯一"
    )
    meta_json: dict[str, Any] | None = Field(
        default=None,
        description='扩展属性（JSON 对象，如 {"diary_date":"2026-09-28"}）；内核不解释，归外壳模块用',
    )
    sort: int = Field(default=0, description="同层排序权重（越小越靠前，默认 0）")


class DocsNodeUpdate(BaseModel):
    """改名 / 移动(parent_id) / 改 meta_json / 改 sort。"""

    parent_id: str | None = Field(
        default=None, description="移动到新的父节点；传 null = 移到根。不许移到自己或自己的子孙下（防环）"
    )
    name: str | None = Field(default=None, max_length=200, description="改名（不传=不改）")
    meta_json: dict[str, Any] | None = Field(
        default=None, description="**整体替换**扩展属性（不是合并）——要保留原属性请连原属性一起传"
    )
    sort: int | None = Field(default=None, description="同层排序权重")


class DocsContentIn(BaseModel):
    """保存正文。"""

    format: str = Field(default="md", description="txt | md")
    body: str = Field(default="", description="正文")


class DocsContentByPathIn(BaseModel):
    """按路径写正文（AI 友好 · 2026-09-27 · 主人「补 docs.content.write」）。

    为什么需要它：MCP 工具面只暴露**无路径参数**的端点 ——
    `PUT /nodes/{id}/content` 带 `{id}`，而桥接层**不做路径参数替换**，
    于是 AI 拿不到"先查 id 再写"的入口（实测：只能建节点、写不了正文）。
    本 schema 给出一条「**说清路径就能写**」的路：一次调用完成
    「建文件夹 -> 建文档 -> 写正文」，与前端树用的 id 入口并存、互不取代。
    """

    path: str = Field(
        min_length=1,
        max_length=500,
        description="从根开始的路径，用 / 分层（如「线上课/计算机视觉」）",
    )
    format: str = Field(default="md", description="txt | md")
    body: str = Field(default="", description="正文")
    create_if_missing: bool = Field(
        default=True, description="路径缺段时按需创建（中段建 folder、末段建 doc）"
    )


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
