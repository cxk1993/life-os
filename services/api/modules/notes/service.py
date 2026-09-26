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
from .schema import LibCreate, NoteCreate, NoteUpdate


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
        terms = [t for t in (q or "").replace('"', " ").split() if t]
        stmt = select(NoteIndex)
        if lib_id:
            stmt = stmt.where(NoteIndex.lib_id == lib_id)
        if terms:
            cond = None
            for t in terms:
                like = f"%{t}%"
                c = col(NoteIndex.title).like(like) | col(NoteIndex.excerpt).like(like)
                cond = c if cond is None else (cond | c)
            stmt = stmt.where(cond)
        stmt = stmt.order_by(col(NoteIndex.mtime).desc()).limit(min(limit, 200))
        rows = list(self.db.exec(stmt).all())
        lib_keys = {lib.id: lib.key for lib in self.db.exec(select(NoteLib)).all()}
        items = []
        for r in rows:
            b = _dump_brief(r, lib_keys.get(r.lib_id, ""))
            if terms:
                title = str(b.get("title") or "")
                ex = str(b.get("excerpt") or "")
                score = 0.0
                covered = True
                for t in terms:
                    in_t = t.lower() in title.lower()
                    in_e = t.lower() in ex.lower()
                    if not (in_t or in_e):
                        covered = False
                        break
                    score += 3.0 if in_t else 0.0
                    score += 1.0 if in_e else 0.0
                if not covered:
                    continue
                hl = ex
                for t in sorted(terms, key=len, reverse=True):
                    if t and t.lower() in hl.lower():
                        # 简单标记第一处
                        import re as _re

                        hl = _re.sub(
                            _re.escape(t), lambda m: f"[[{m.group(0)}]]", hl, count=1, flags=_re.I
                        )
                b["score"] = score
                b["highlight"] = hl[:160]
            items.append(b)
        items.sort(key=lambda x: (-float(x.get("score") or 0), -int(x.get("mtime") or 0)))
        return {"items": items, "total": len(items)}

    def get_attachment(self, lib_key: str, path: str) -> tuple[bytes, str]:
        """★ 读二进制附件（astrbot 下场 · 主人⑤「ob 附件、图片插入要能正常展示」）。

        默认库 key = "attach"（桥 config.yaml 的附件库，指向主人 obsidian 附件文件夹）。
        """
        lib = self.db.exec(select(NoteLib).where(NoteLib.key == lib_key)).first()
        if lib is None:
            raise NotFoundError(f"未知库：{lib_key}")
        try:
            return self.bridge.attachment(lib.key, path)
        except BridgeError as exc:
            raise ServiceUnavailableError(exc.detail) from exc

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
            # ★ 兜底回退（astrbot 下场）：空标题 → 文件名（防桥侧旧版本/空文件）
            _t = str(e.get("title") or "").strip()
            if not _t:
                _t = str(e.get("rel_path") or "").rsplit("/", 1)[-1].rsplit(".", 1)[0]
            row.title = _t[:200]
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
    # ───────────────────────── 笔记 CRUD ─────────────────────────

    def create_note(self, lib_id: str, body: NoteCreate) -> dict[str, Any]:
        """新建笔记（写到本机桥）。"""
        lib = self._require_lib(lib_id)
        if not lib.enabled:
            raise ValidationError(f"库 {lib.key} 已禁用，先启用再创建")

        now = datetime.now(UTC)
        row = NoteIndex(
            lib_id=lib.id,
            rel_path=body.rel_path,
            title=body.title or body.rel_path.split("/")[-1],
            mtime=int(now.timestamp()),
            size=len(body.content.encode("utf-8")),
            synced_at=now,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)

        # 写到本机桥
        try:
            self.bridge.write(lib.key, body.rel_path, body.content)
        except BridgeError as exc:
            self.db.rollback()
            raise ValidationError(f"写入失败：{exc.detail}") from exc

        return _dump_brief(row, lib.key)

    def update_note(self, note_id: str, body: NoteUpdate) -> dict[str, Any]:
        """更新笔记（写到本机桥）。"""
        row = self.db.get(NoteIndex, note_id)
        if row is None:
            raise NotFoundError(f"笔记不存在：{note_id}")

        lib = self._require_lib(row.lib_id)
        brief = _dump_brief(row, lib.key)

        # 读取当前内容
        current_content = ""
        try:
            data = self.bridge.read(lib.key, row.rel_path)
            current_content = str(data.get("content") or "")
        except BridgeError:
            pass

        # 合并更新
        new_content = body.content if body.content is not None else current_content
        new_title = body.title if body.title is not None else row.title

        # 写回本机桥
        try:
            self.bridge.write(lib.key, row.rel_path, new_content, title=new_title)
        except BridgeError as exc:
            raise ValidationError(f"写入失败：{exc.detail}") from exc

        # 更新索引
        row.title = new_title
        row.mtime = int(datetime.now(UTC).timestamp())
        row.size = len(new_content.encode("utf-8"))
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)

        return _dump_brief(row, lib.key)

    def delete_note(self, note_id: str) -> None:
        """删除笔记（删本机桥 + 索引）。"""
        row = self.db.get(NoteIndex, note_id)
        if row is None:
            raise NotFoundError(f"笔记不存在：{note_id}")

        lib = self._require_lib(row.lib_id)

        # 删本机桥
        try:
            self.bridge.delete(lib.key, row.rel_path)
        except BridgeError:
            pass  # 删不掉也继续

        self.db.delete(row)
        self.db.commit()
    # ───────────────────────── 文件夹结构树 ─────────────────────────

    def get_tree(self, lib_id: str) -> dict[str, Any]:
        """按 rel_path 解析文件夹层级。"""
        lib = self._require_lib(lib_id)
        rows = self.db.exec(
            select(NoteIndex).where(NoteIndex.lib_id == lib.id)
        ).all()

        # 构建树
        root: dict[str, Any] = {
            "id": lib.id,
            "title": lib.name,
            "rel_path": "",
            "is_dir": True,
            "children": [],
        }

        for row in rows:
            parts = row.rel_path.split("/")
            node = root
            for i, part in enumerate(parts[:-1]):
                # 找或创建目录
                found = None
                for child in node["children"]:
                    if child["title"] == part and child["is_dir"]:
                        found = child
                        break
                if found is None:
                    found = {
                        "id": f"{lib.id}/{'/'.join(parts[:i+1])}",
                        "title": part,
                        "rel_path": "/".join(parts[:i+1]),
                        "is_dir": True,
                        "children": [],
                    }
                    node["children"].append(found)
                node = found

            # 添加文件
            node["children"].append({
                "id": row.id,
                "title": row.title or parts[-1],
                "rel_path": row.rel_path,
                "is_dir": False,
            })

        # 排序：目录在前，文件在后
        def sort_children(node: dict) -> None:
            node["children"].sort(key=lambda c: (not c["is_dir"], c["title"]))
            for child in node["children"]:
                if child["is_dir"]:
                    sort_children(child)

        sort_children(root)

        return {"lib_id": lib.id, "lib_key": lib.key, "root": root}
