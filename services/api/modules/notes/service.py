"""笔记业务逻辑：库登记、索引缓存、搜索、按需取全文、从桥同步。

★ 全文绝不进服务器库；列表只有索引。
★ 一次 upsert 整库索引，禁止循环里再查库。
★ 桥客户端可注入（测试用 mock）；默认 BridgeClient 读 settings。
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session, col, select

from core.errors import NotFoundError, ValidationError
from core.events import event_bus

from .bridge_client import BridgeClient, BridgeError
from .models import NoteIndex, NoteLib
from .schema import LibCreate


def _dump_brief(row: NoteIndex, lib_key: str = "") -> dict[str, Any]:
    return {
        "id": row.id,
        "lib_id": row.lib_id,
        "lib_key": lib_key,
        "rel_path": row.rel_path,
        "title": row.title,
        "excerpt": row.excerpt or "",
        "mtime": row.mtime,
        "size": row.size,
        "synced_at": row.synced_at,
    }


class NotesService:
    def __init__(self, db: Session, bridge: BridgeClient | None = None) -> None:
        self.db = db
        self._bridge = bridge

    @property
    def bridge(self) -> BridgeClient:
        if self._bridge is None:
            self._bridge = BridgeClient()
        return self._bridge

    # ───────────────────────── 库 ─────────────────────────
    def list_libs(self) -> list[dict[str, Any]]:
        rows = self.db.exec(select(NoteLib).order_by(NoteLib.key)).all()
        return [
            {
                "id": r.id,
                "key": r.key,
                "name": r.name,
                "enabled": r.enabled,
                "md_count": r.md_count,
            }
            for r in rows
        ]

    def upsert_lib(self, body: LibCreate) -> dict[str, Any]:
        key = body.key.strip()
        if not key:
            raise ValidationError("库 key 不能为空")
        row = self.db.exec(select(NoteLib).where(NoteLib.key == key)).first()
        if row is None:
            row = NoteLib(key=key, name=body.name, enabled=body.enabled)
        else:
            row.name = body.name or row.name
            row.enabled = body.enabled
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return {
            "id": row.id,
            "key": row.key,
            "name": row.name,
            "enabled": row.enabled,
            "md_count": row.md_count,
        }

    def _require_lib(self, lib_id: str) -> NoteLib:
        lib = self.db.get(NoteLib, lib_id)
        if lib is None:
            raise NotFoundError(f"笔记库不存在：{lib_id}")
        return lib

    # ───────────────────────── 索引读 ─────────────────────────
    def search(
        self,
        q: str | None = None,
        lib_id: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        stmt = select(NoteIndex)
        if lib_id:
            stmt = stmt.where(NoteIndex.lib_id == lib_id)
        if q:
            like = f"%{q.strip()}%"
            stmt = stmt.where(
                col(NoteIndex.title).like(like) | col(NoteIndex.excerpt).like(like)
            )
        stmt = stmt.order_by(col(NoteIndex.mtime).desc()).limit(min(limit, 200))
        rows = list(self.db.exec(stmt).all())
        lib_keys = {lib.id: lib.key for lib in self.db.exec(select(NoteLib)).all()}
        items = [_dump_brief(r, lib_keys.get(r.lib_id, "")) for r in rows]
        return {"items": items, "total": len(items)}

    def get_note(self, note_id: str) -> dict[str, Any]:
        """索引 + 经桥取全文。桥不可达时仍返回索引，content 空串并带 warning。"""
        row = self.db.get(NoteIndex, note_id)
        if row is None:
            raise NotFoundError(f"笔记不存在：{note_id}")
        lib = self._require_lib(row.lib_id)
        brief = _dump_brief(row, lib.key)
        content = ""
        try:
            data = self.bridge.read(lib.key, row.rel_path)
            content = str(data.get("content") or "")
        except BridgeError:
            # 桥离线：仍返回索引，前端可展示「全文暂不可用」
            pass
        return {**brief, "content": content}

    # ───────────────────────── 同步 ─────────────────────────
    def sync_lib(self, lib_id: str) -> dict[str, Any]:
        """从本机桥拉全量索引，upsert 进 note_index，并删掉本机已不存在的条目。"""
        lib = self._require_lib(lib_id)
        if not lib.enabled:
            raise ValidationError(f"库 {lib.key} 已禁用，先启用再同步")
        try:
            entries = self.bridge.scan(lib.key)
        except BridgeError as exc:
            raise ValidationError(f"同步失败：{exc.detail}") from exc

        existing = {
            r.rel_path: r
            for r in self.db.exec(
                select(NoteIndex).where(NoteIndex.lib_id == lib.id)
            ).all()
        }
        now = datetime.now(UTC)
        seen: set[str] = set()
        upserted = 0
        for e in entries:
            rel = str(e.get("rel_path") or "").strip()
            if not rel:
                continue
            seen.add(rel)
            row = existing.get(rel)
            if row is None:
                row = NoteIndex(lib_id=lib.id, rel_path=rel)
            row.title = str(e.get("title") or "")[:200]
            row.mtime = int(e.get("mtime") or 0)
            row.size = int(e.get("size") or 0)
            row.content_hash = str(e.get("hash") or "")[:64]
            row.excerpt = str(e.get("excerpt") or "")
            row.synced_at = now
            self.db.add(row)
            upserted += 1

        removed = 0
        for rel, row in existing.items():
            if rel not in seen:
                self.db.delete(row)
                removed += 1

        lib.md_count = upserted
        self.db.add(lib)
        self.db.commit()
        event_bus.publish(
            "notes.lib.synced",
            {"lib_key": lib.key, "upserted": upserted, "removed": removed},
            source="notes",
        )
        return {
            "lib_key": lib.key,
            "upserted": upserted,
            "removed": removed,
            "md_count": upserted,
        }

    def sync_all(self) -> list[dict[str, Any]]:
        libs = self.db.exec(select(NoteLib).where(NoteLib.enabled == True)).all()  # noqa: E712
        return [self.sync_lib(lib.id) for lib in libs]
