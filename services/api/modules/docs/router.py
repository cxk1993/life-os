"""文档树内核路由（薄：只做参数校验 + 调 service + 发事件）。

HTTP 契约（全项目统一，不许自创）：
  成功 → 直接返回资源 JSON（200/201）
  失败 → 由内核统一转成 RFC7807 application/problem+json

★ 前缀由内核按 manifest.api.base 自动加，这里不要写 prefix=。
★ 事件总线：写操作在 service 层 publish 到 event_bus，内核 SSE 自动下推。
★ 幂等（Idempotency-Key）由内核自动处理，这里不重复做。
★ 路径参数用 Annotated[str, FPath(...)]（不是 = FPath(...)）。
★ 本文件不要加 `from __future__ import annotations`：
  它会把 `-> None` 变成字符串 "None" → get_type_hints 得到 NoneType（truthy）
  → FastAPI 认为 204 带了响应体 → 整个后端起不来。
"""

import json
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from fastapi import Path as FPath
from sqlmodel import Session

from core.deps import get_current_user, get_db
from core.security import User

from .schema import (
    DocsContentIn,
    DocsNodeCreate,
    DocsNodeDetailOut,
    DocsNodeOut,
    DocsNodeUpdate,
    DocsTreeNode,
)
from .schema import DocsContentByPathIn  # 2026-09-27 按路径写正文（AI 友好入口）
from .service import DocsService

router = APIRouter()

_MANIFEST_PATH = Path(__file__).resolve().parent / "manifest.json"
with _MANIFEST_PATH.open(encoding="utf-8") as _f:
    _MANIFEST = json.load(_f)

DbDep = Session
UserDep = User


@router.get("/health")
def health() -> dict[str, bool]:
    """每个插件都必须有 health —— 内核据此判断"该能力是否可用"。"""
    return {"ok": True}


@router.get("/manifest")
def manifest() -> dict:
    """模块清单（前端 / AI 发现能力用）。"""
    return _MANIFEST


@router.get("/nodes", response_model=list[DocsTreeNode])
def get_tree(
    root: str | None = Query(None, description="根节点 id；缺省 = 整片森林"),
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """树查询：返回以 root 为顶点的完整子树，一次装配（禁止 N+1）。"""
    return DocsService(db).get_tree(root)


@router.post("/nodes", response_model=DocsNodeOut, status_code=status.HTTP_201_CREATED)
def create_node(
    body: DocsNodeCreate,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    return DocsService(db).create(body)


@router.get("/nodes/{node_id}", response_model=DocsNodeDetailOut)
def get_node(
    node_id: Annotated[str, FPath(description="节点 id")],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """节点 + 正文。"""
    return DocsService(db).get(node_id)


@router.patch("/nodes/{node_id}", response_model=DocsNodeOut)
def update_node(
    node_id: Annotated[str, FPath(description="节点 id")],
    body: DocsNodeUpdate,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """改名 / 移动(parent_id) / 改 meta_json / 改 sort。"""
    return DocsService(db).update(node_id, body)


@router.delete("/nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_node(
    node_id: Annotated[str, FPath(description="节点 id")],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> None:
    """软删（进回收站，可恢复）。"""
    DocsService(db).soft_delete(node_id)


@router.get("/trash", response_model=dict)
def list_trash(
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = Query(None, description="分页游标（opaque）"),
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """回收站列表（cursor 分页）。"""
    items, next_cursor = DocsService(db).list_trash(limit=limit, cursor=cursor)
    return {"items": items, "next_cursor": next_cursor}


@router.post("/trash/{node_id}/restore", response_model=DocsNodeOut)
def restore_node(
    node_id: Annotated[str, FPath(description="节点 id")],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    return DocsService(db).restore(node_id)


@router.delete("/trash/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
def purge_node(
    node_id: Annotated[str, FPath(description="节点 id")],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> None:
    """彻底删除（硬删，清 content/revisions/fts）。"""
    DocsService(db).hard_delete(node_id)


@router.post("/content", response_model=DocsNodeDetailOut)
def post_content_by_path(
    body: DocsContentByPathIn,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """按路径写正文（AI 友好）：一次调用完成「建文件夹 -> 建文档 -> 写正文」。

    与 `PUT /nodes/{node_id}/content` 的分工：
      前者面向**已经知道 id** 的调用方（前端文档树）；
      本端点面向**只知道路径**的调用方（AI / MCP 工具面），
      也正好绕开"桥接层不做路径参数替换"这条硬限制。
    """
    return DocsService(db).upsert_content_by_path(body)


@router.put("/nodes/{node_id}/content", response_model=DocsNodeDetailOut)
def save_content(
    node_id: Annotated[str, FPath(description="节点 id")],
    body: DocsContentIn,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """保存正文（自动写版本快照 + 同步 FTS）。"""
    return DocsService(db).save_content(node_id, body)


@router.get("/nodes/{node_id}/revisions", response_model=dict)
def list_revisions(
    node_id: Annotated[str, FPath(description="节点 id")],
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = Query(None, description="分页游标（opaque）"),
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """版本列表（cursor 分页，新的在前）。"""
    items, next_cursor = DocsService(db).list_revisions(node_id, limit=limit, cursor=cursor)
    return {"items": items, "next_cursor": next_cursor}


@router.get("/nodes/{node_id}/revisions/{rev_id}", response_model=dict)
def get_revision(
    node_id: Annotated[str, FPath(description="节点 id")],
    rev_id: Annotated[str, FPath(description="版本 id")],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    return DocsService(db).get_revision(node_id, rev_id)


@router.post("/nodes/{node_id}/revisions/{rev_id}/restore", response_model=DocsNodeDetailOut)
def restore_revision(
    node_id: Annotated[str, FPath(description="节点 id")],
    rev_id: Annotated[str, FPath(description="版本 id")],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """回退到某版本（回退本身也产生一条新 revision，历史不丢）。"""
    return DocsService(db).restore_revision(node_id, rev_id)


@router.get("/search", response_model=dict)
def search(
    q: str = Query(..., description="检索词（标题/正文，中文友好）"),
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = Query(None, description="分页游标（opaque）"),
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """检索：FTS5 MATCH，cursor 分页，软删节点不进结果。"""
    items, next_cursor = DocsService(db).search(q=q, limit=limit, cursor=cursor)
    return {"items": items, "next_cursor": next_cursor}
