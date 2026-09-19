"""能力目录业务：四源合并（plugin / web_entry / kernel / manual）。

★「照镜子」原则：清单从数据来，不许写死。目录内容随四源实时变化。
★ 插件之间不 import / 不 join：web_entry 源经 ISSUE-005 A 案 get_plugin_client
  跨插件调 T19 API；plugin 源由 router 传 app.state.modules（注册表实时）。
★ kernel 源 = 静态声明文件（不写死在业务代码里）。
★ manual 源 = 自己的表（catalog_entry），每条独立 enabled 开关。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlmodel import Session, col, select

from core.errors import NotFoundError, ValidationError
from db.base import utcnow

from .models import CatalogEntry, caps_to_json
from .schema import (
    CapabilityEntryOut,
    ManualEntryCreate,
    ManualEntryUpdate,
    normalize_auth_ref,
    normalize_kind,
    normalize_url,
)

# 内置插件里哪些不算业务能力（内核服务模块，不列入目录的 plugin 源）
_NON_CAPABILITY_MODULES = {"auth", "plugins", "web", "catalog"}

# kernel 静态声明文件
_KERNEL_FILE = Path(__file__).resolve().parent / "kernel_capabilities.json"


def _load_kernel_entries() -> list[dict[str, Any]]:
    with _KERNEL_FILE.open(encoding="utf-8") as f:
        data = json.load(f)
    entries = data.get("entries", [])
    # ★ 文件顶层写 source=kernel，但条目数组内每条也要带 source，
    #   否则合并时 source 缺省成 "manual"，kernel 分组消失。
    for e in entries:
        e.setdefault("source", "kernel")
    return entries


class CatalogService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ───────────────────────── manual 源（自己的表） ─────────────────────────

    def list_manual(self) -> list[dict[str, Any]]:
        stmt = select(CatalogEntry).order_by(col(CatalogEntry.created_at))
        rows = list(self.db.exec(stmt).all())
        return [r.to_capability() for r in rows]

    def get_manual(self, entry_id: str) -> CatalogEntry:
        """按对外 id 查手动条目。

        create 返回的对外 id 是 catalog_id（如 manual-xxx），不是主键；
        这里先按主键再按 catalog_id 兜底，保证 PATCH/DELETE 用返回的 id 能命中。
        """
        row = self.db.get(CatalogEntry, entry_id)
        if row is None:
            row = self.db.exec(
                select(CatalogEntry).where(col(CatalogEntry.catalog_id) == entry_id)
            ).first()
        if row is None:
            raise NotFoundError(f"手动条目不存在：{entry_id}")
        return row

    def create_manual(self, body: ManualEntryCreate) -> dict[str, Any]:
        kind = normalize_kind(body.kind)
        url = normalize_url(body.url) if body.url else None
        auth_ref = normalize_auth_ref(body.auth_ref)
        if kind != "web" and not (body.endpoint or "").strip():
            raise ValidationError(
                "kind 非 web 时必须给 endpoint（声明了能力却没地方调 = 骗 agent）"
            )

        catalog_id = (body.catalog_id or "").strip() or None
        if catalog_id is None:
            import uuid

            catalog_id = f"manual-{uuid.uuid4().hex[:10]}"

        row = CatalogEntry(
            name=(body.name or "").strip(),
            kind=kind,
            url=url,
            endpoint=(body.endpoint or "").strip() or None,
            auth_ref=auth_ref,
            capabilities=caps_to_json(body.capabilities),
            note=body.note,
            enabled=body.enabled,
            catalog_id=catalog_id,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row.to_capability()

    def update_manual(self, entry_id: str, body: ManualEntryUpdate) -> dict[str, Any]:
        row = self.get_manual(entry_id)
        data = body.model_dump(exclude_unset=True)

        if "name" in data and data["name"] is not None:
            row.name = data["name"].strip()
        if "kind" in data and data["kind"] is not None:
            row.kind = normalize_kind(data["kind"])
        if "url" in data and data["url"] is not None:
            row.url = normalize_url(data["url"])
        if "endpoint" in data and data["endpoint"] is not None:
            row.endpoint = (data["endpoint"] or "").strip() or None
        if "auth_ref" in data:
            row.auth_ref = normalize_auth_ref(data["auth_ref"])
        if "capabilities" in data and data["capabilities"] is not None:
            row.capabilities = caps_to_json(data["capabilities"])
        if "note" in data and data["note"] is not None:
            row.note = data["note"] or None
        if "enabled" in data and data["enabled"] is not None:
            row.enabled = bool(data["enabled"])

        row.updated_at = utcnow()
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row.to_capability()

    def delete_manual(self, entry_id: str) -> None:
        row = self.get_manual(entry_id)
        self.db.delete(row)
        self.db.commit()

    # ───────────────────────── plugin 源（注册表实时） ─────────────────────────

    @staticmethod
    def _plugin_entries(modules: dict[str, Any]) -> list[dict[str, Any]]:
        """从内核模块注册表读每个插件的 manifest.provides 生成条目。

        modules: app.state.modules（id -> manifest dict）；每请求现读，不做缓存表。
        """
        entries: list[dict[str, Any]] = []
        for pid, manifest in modules.items():
            if pid in _NON_CAPABILITY_MODULES:
                continue
            provides = manifest.get("provides") or []
            if not provides:
                continue
            base = (manifest.get("api") or {}).get("base", f"/api/v1/{pid}")
            entries.append(
                {
                    "id": f"plugin.{pid}",
                    "name": manifest.get("name", pid),
                    "kind": "web+rest",
                    "url": None,
                    "endpoint": base,
                    "auth_ref": "none",
                    "capabilities": list(provides),
                    "enabled": True,
                    "note": manifest.get("description"),
                    "source": "plugin",
                }
            )
        return entries

    # ───────────────────────── web_entry 源（经 T19 API） ─────────────────────────

    @staticmethod
    def _web_entry_entries(client: Any) -> list[dict[str, Any]]:
        """经 ISSUE-005 A 案 get_plugin_client 跨插件调 T19 API。

        失败时降级返回空列表（该能力不可用，不报错——ADR-0002 优雅降级）。
        """
        if client is None:
            return []
        try:
            data = client.get("/api/v1/web/entries?enabled=true")
            items = data.get("items", []) if isinstance(data, dict) else []
            out: list[dict[str, Any]] = []
            for it in items:
                cap = it.get("capability")
                if isinstance(cap, dict):
                    out.append(cap)
            return out
        except Exception:
            # T19 不可用时目录降级（不含 web_entry 源），不报错
            return []

    # ───────────────────────── 合并 ─────────────────────────

    def catalog(
        self,
        modules: dict[str, Any],
        web_client: Any = None,
    ) -> dict[str, Any]:
        """四源合并 → 全量目录。

        modules: app.state.modules（plugin 源）
        web_client: get_plugin_client 返回的 internal client（web_entry 源）；
                    None = T19 不可用（降级）
        """
        plugin_entries = self._plugin_entries(modules)
        web_entries = self._web_entry_entries(web_client)
        kernel_entries = _load_kernel_entries()
        manual_entries = self.list_manual()

        all_entries: list[dict[str, Any]] = []
        all_entries.extend(plugin_entries)
        all_entries.extend(web_entries)
        all_entries.extend(kernel_entries)
        all_entries.extend(manual_entries)

        counts: dict[str, int] = {}
        for e in all_entries:
            src = e.get("source", "manual")
            counts[src] = counts.get(src, 0) + 1

        # 统一转成对外形状
        shaped = [CapabilityEntryOut(**e).model_dump() for e in all_entries]

        return {
            "entries": shaped,
            "generatedAt": datetime.now(timezone.utc),  # noqa: UP017（项目惯例 timezone.utc）
            "counts": counts,
        }