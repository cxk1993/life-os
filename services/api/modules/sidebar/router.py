"""侧栏自定义容器路由（TX-SIDEBAR-02）。"""
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
    return {"ok": True}


@router.get("/manifest")
def manifest() -> dict:
    return _MANIFEST


@router.get("/items", response_model=ListOut)
def list_items(
    enabled_only: bool = Query(False),
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    items = SidebarService(db).list_items(enabled_only)
    return {"items": items, "count": len(items)}


@router.post("/items", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
def create_item(
    body: ItemCreate,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    return SidebarService(db).create(body)


@router.get("/items/{item_id}", response_model=ItemOut)
def get_item(
    item_id: Annotated[str, FPath()],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    return SidebarService(db).get(item_id)


@router.patch("/items/{item_id}", response_model=ItemOut)
def update_item(
    item_id: Annotated[str, FPath()],
    body: ItemUpdate,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    return SidebarService(db).update(item_id, body)


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(
    item_id: Annotated[str, FPath()],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> None:
    SidebarService(db).delete(item_id)


@router.post("/items/reorder")
def reorder(
    body: ReorderIn,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
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
    return SidebarService(db).export()
