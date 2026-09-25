"""侧栏条目 CRUD。"""
from __future__ import annotations

from typing import Any

from sqlmodel import Session, col, select

from core.errors import NotFoundError

from .models import SidebarItem
from .schema import ItemCreate, ItemUpdate


class SidebarService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _dump(self, r: SidebarItem) -> dict[str, Any]:
        return {
            "id": str(r.id),
            "type": r.type,
            "label": r.label,
            "icon": r.icon,
            "abbr": r.abbr,
            "href": r.href,
            "target": r.target,
            "body": r.body,
            "node_ref": r.node_ref,
            "description": r.description,
            "group": r.group,
            "order": r.sort,
            "enabled": r.enabled,
            "pinned": r.pinned,
            "created_at": r.created_at,
            "updated_at": r.updated_at,
        }

    def list_items(self, enabled_only: bool = False) -> list[dict[str, Any]]:
        stmt = select(SidebarItem).order_by(
            col(SidebarItem.group), col(SidebarItem.sort), col(SidebarItem.label)
        )
        if enabled_only:
            stmt = stmt.where(col(SidebarItem.enabled) == True)  # noqa: E712
        return [self._dump(r) for r in self.db.exec(stmt).all()]

    def get(self, item_id: str) -> dict[str, Any]:
        r = self.db.get(SidebarItem, item_id)
        if r is None:
            raise NotFoundError("sidebar item not found")
        return self._dump(r)

    def create(self, body: ItemCreate) -> dict[str, Any]:
        r = SidebarItem(
            type=body.type,
            label=body.label,
            icon=body.icon,
            abbr=body.abbr,
            href=body.href,
            target=body.target,
            body=body.body,
            node_ref=body.node_ref,
            description=body.description,
            group=body.group,
            sort=body.order,
            enabled=body.enabled,
            pinned=body.pinned,
        )
        self.db.add(r)
        self.db.commit()
        self.db.refresh(r)
        return self._dump(r)

    def update(self, item_id: str, body: ItemUpdate) -> dict[str, Any]:
        r = self.db.get(SidebarItem, item_id)
        if r is None:
            raise NotFoundError("sidebar item not found")
        data = body.model_dump(exclude_unset=True)
        if "order" in data:
            r.sort = data.pop("order")
        for k, v in data.items():
            setattr(r, k, v)
        self.db.add(r)
        self.db.commit()
        self.db.refresh(r)
        return self._dump(r)

    def delete(self, item_id: str) -> None:
        r = self.db.get(SidebarItem, item_id)
        if r is None:
            raise NotFoundError("sidebar item not found")
        self.db.delete(r)
        self.db.commit()

    def export(self) -> dict[str, Any]:
        return {"items": self.list_items(), "schema_version": "sidebar-0.2"}
