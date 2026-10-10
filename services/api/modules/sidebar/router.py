"""侧栏自定义容器路由。"""
import json
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from fastapi import Path as FPath
from sqlmodel import Session

from core.deps import get_current_user, get_db
from core.security import User

from .schema import ItemCreate, ItemOut, ItemUpdate, ListOut, ReorderIn
from .service import SidebarService

router = APIRouter()

_MANIFEST_PATH = Path(__file__).resolve().parent / "manifest.json"
with _MANIFEST_PATH.open(encoding="utf-8") as _f:
    _MANIFEST = json.load(_f)

DbDep = Session
UserDep = User


@router.get("/health")
def health() -> dict[str, bool]:
    """插件健康探针（恒 200）。"""
    return {"ok": True}


@router.get("/manifest")
def manifest() -> dict:
    """模块清单（前端 / AI 发现能力用）。"""
    return _MANIFEST


@router.get("/items", response_model=ListOut)
def list_items(
    enabled_only: bool = Query(False, description="true=只看启用的项（默认全部）"),
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """列出侧栏项（`enabled_only=true` 只看启用的项）；返回含 `count`。"""
    items = SidebarService(db).list_items(enabled_only)
    return {"items": items, "count": len(items)}


@router.post("/items", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
def create_item(
    body: ItemCreate,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """新建一个侧栏项（link / note / announcement / friend-link）。

    ⚠️ `href` 必须是**绝对 http(s) URL**，且**仅 link/friend-link 必填**；
    ⚠️ `body` **一律不收**，正文请用 `node_ref`。
    """
    return SidebarService(db).create(body)


@router.get("/items/{item_id}", response_model=ItemOut)
def get_item(
    item_id: Annotated[str, FPath(description="侧栏项 id —— 从 GET /items 的结果里取")],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """读单个侧栏项。"""
    return SidebarService(db).get(item_id)


@router.patch("/items/{item_id}", response_model=ItemOut)
def update_item(
    item_id: Annotated[str, FPath(description="侧栏项 id —— 从 GET /items 的结果里取")],
    body: ItemUpdate,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """改一个侧栏项（任意字段）。⚠️ 改 `type` 会重新套用 href 白名单。"""
    return SidebarService(db).update(item_id, body)


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(
    item_id: Annotated[str, FPath(description="侧栏项 id —— 从 GET /items 的结果里取")],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> None:
    """删除一个侧栏项。"""
    SidebarService(db).delete(item_id)


@router.post("/items/reorder")
def reorder(
    body: ReorderIn,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """**整组重排**：`ids` 是侧栏项的**完整新顺序**（不是增量交换）。

    传进来的顺序即最终顺序；未列出的项会被视为排在有列表项之后。
    """
    svc = SidebarService(db)
    for i, iid in enumerate(body.ids):
        try:
            svc.update(iid, ItemUpdate(order=i))
        except Exception:  # noqa: BLE001
            continue
    items = svc.list_items()
    return {"items": items, "count": len(items)}


@router.get("/export")
def export_items(
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """导出侧栏配置（备份 / 搬家用）。"""
    return SidebarService(db).export()
