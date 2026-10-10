"""docs 业务逻辑：树装配 / 移动防环 / 版本快照回退 / FTS5 同步 / 软删回收站 / 检索。

★ 一次查、禁止 N+1：GET /nodes 用一次 SELECT 捞回整棵子树，内存哈希组装。
★ 移动防环：目标 parent_id 不能是自己或自己的子孙（沿 parent_id 向上爬，O(深度)）。
★ 版本历史：保存正文即快照；回退保留历史（回退本身也产生一条新 revision）。
★ FTS 同步：节点/正文增改删时由 service 层同步维护 docs_fts（不用触发器）。
★ 软删：deleted_at 非空即视为已删；回收站列出软删节点；彻底删除清 content/revisions/fts。
"""

from __future__ import annotations

import json
from typing import Any, TypeVar

from sqlalchemy import text
from sqlmodel import Session, SQLModel, col, select

from core.errors import NotFoundError, ValidationError
from core.events import event_bus
from db.base import utcnow
from db.repo import decode_cursor, encode_cursor

from .models import DocsContent, DocsNode, DocsRevision

_T = TypeVar("_T", bound=SQLModel)


def meta_load(raw: str | None) -> dict[str, Any] | None:
    """DB 的 meta_json 字符串 → dict（空/非法 → None）。"""
    if not raw:
        return None
    try:
        val = json.loads(raw)
        return val if isinstance(val, dict) else None
    except (json.JSONDecodeError, TypeError):
        return None


def meta_dump(meta: dict[str, Any] | None) -> str | None:
    """dict → DB 字符串（空 dict / None → None，不占空间）。"""
    if not meta:
        return None
    return json.dumps(meta, ensure_ascii=False)


def _dump_node(n: DocsNode) -> dict[str, Any]:
    """节点 → 资源 JSON（轻量列，不含正文）。"""
    return {
        "id": n.id,
        "parent_id": n.parent_id,
        "kind": n.kind,
        "name": n.name,
        "sort": n.sort,
        "meta_json": meta_load(n.meta_json),
        "created_at": n.created_at,
        "updated_at": n.updated_at,
        "deleted_at": n.deleted_at,
    }


def _dump_detail(n: DocsNode, content: DocsContent | None) -> dict[str, Any]:
    """节点 + 正文。"""
    d = _dump_node(n)
    d["format"] = content.format if content else None
    d["body"] = content.body if content else None
    return d


class DocsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ───────────────────────── 树查询（一次查，禁 N+1） ─────────────────────────
    def get_tree(self, root: str | None = None) -> list[dict[str, Any]]:
        """返回以 root（默认 NULL=整片森林）为顶点的完整子树。

        一次 SELECT 捞回目标子树全部未删节点，内存里用 parent_id 哈希组装。
        排序：同层 (sort, name, created_at)。
        """
        conds: list[Any] = [col(DocsNode.deleted_at).is_(None)]
        if root is not None:
            conds.append(col(DocsNode.id) == root)
        else:
            conds.append(col(DocsNode.parent_id).is_(None))
        # 先拿根，再一次性把整片森林都取回（自关联没有层级上限，取全部未删）
        rows = list(self.db.exec(select(DocsNode).where(col(DocsNode.deleted_at).is_(None))).all())
        if root is not None:
            root_node = self.db.get(DocsNode, root)
            if root_node is None or root_node.deleted_at is not None:
                raise NotFoundError(f"节点不存在：{root}")
            rows = [r for r in rows if r.id == root or _is_descendant_of(r, root_node, rows)]
        return _assemble(rows, root)

    # ───────────────────────── 节点 CRUD ─────────────────────────
    def create(self, body: Any) -> dict[str, Any]:
        kind = body.kind
        if kind not in ("folder", "doc"):
            raise ValidationError(f"kind 只能是 folder|doc，收到 {kind!r}")
        name = (body.name or "").strip()
        if not name:
            raise ValidationError("name 不能为空")
        if body.parent_id is not None:
            parent = self.db.get(DocsNode, body.parent_id)
            if parent is None:
                raise NotFoundError(f"父节点不存在：{body.parent_id}")
            if parent.deleted_at is not None:
                raise ValidationError(f"父节点已在回收站：{body.parent_id}")
            if parent.kind != "folder":
                raise ValidationError(f"父节点必须是 folder，收到 {parent.kind!r}")
        node = DocsNode(
            parent_id=body.parent_id,
            kind=kind,
            name=name,
            sort=body.sort if body.sort is not None else 0,
            meta_json=meta_dump(body.meta_json),
        )
        self.db.add(node)
        self.db.commit()
        self.db.refresh(node)
        if kind == "doc":
            self._sync_fts(node, "")
        event_bus.publish("docs.node.created", _dump_node(node), source="docs")
        return _dump_node(node)

    def get(self, id_: str) -> dict[str, Any]:
        node = self.db.get(DocsNode, id_)
        if node is None or node.deleted_at is not None:
            raise NotFoundError(f"节点不存在：{id_}")
        content = self.db.get(DocsContent, id_)
        return _dump_detail(node, content)

    def update(self, id_: str, body: Any) -> dict[str, Any]:
        node = self.db.get(DocsNode, id_)
        if node is None or node.deleted_at is not None:
            raise NotFoundError(f"节点不存在：{id_}")
        if body.name is not None:
            name = body.name.strip()
            if not name:
                raise ValidationError("name 不能为空")
            node.name = name
        if body.sort is not None:
            node.sort = body.sort
        if body.meta_json is not None:
            node.meta_json = meta_dump(body.meta_json)
        if "parent_id" in body.model_fields_set:
            self._move(node, body.parent_id)
        self.db.add(node)
        self.db.commit()
        self.db.refresh(node)
        self._sync_fts(node)
        event_bus.publish("docs.node.updated", _dump_node(node), source="docs")
        return _dump_node(node)

    def _move(self, node: DocsNode, new_parent_id: str | None) -> None:
        """移动（防环：不能移进自己或自己的子孙）。"""
        if new_parent_id == node.id:
            raise ValidationError("不能把节点移进它自己")
        if new_parent_id is not None:
            parent = self.db.get(DocsNode, new_parent_id)
            if parent is None:
                raise NotFoundError(f"父节点不存在：{new_parent_id}")
            if parent.deleted_at is not None:
                raise ValidationError(f"父节点已在回收站：{new_parent_id}")
            if parent.kind != "folder":
                raise ValidationError(f"父节点必须是 folder，收到 {parent.kind!r}")
            # 防环：沿 parent_id 向上爬，若 node 出现在祖先链中 → 拒绝
            cur: DocsNode | None = parent
            while cur is not None:
                if cur.id == node.id:
                    raise ValidationError("不能把节点移进自己的子孙（防环）")
                cur = self.db.get(DocsNode, cur.parent_id) if cur.parent_id else None
        node.parent_id = new_parent_id

    # ───────────────────────── 软删 / 回收站 / 彻底删除 ─────────────────────────
    def soft_delete(self, id_: str) -> None:
        node = self.db.get(DocsNode, id_)
        if node is None or node.deleted_at is not None:
            raise NotFoundError(f"节点不存在：{id_}")
        node.deleted_at = utcnow()
        self.db.add(node)
        self.db.commit()
        event_bus.publish("docs.node.deleted", {"id": id_}, source="docs")

    def list_trash(
        self, limit: int = 50, cursor: str | None = None
    ) -> tuple[list[dict[str, Any]], str | None]:
        conds = (col(DocsNode.deleted_at).is_not(None),)
        rows, next_cursor = self._page_rows(DocsNode, limit=limit, cursor=cursor, conditions=conds)
        return [_dump_node(r) for r in rows], next_cursor

    def restore(self, id_: str) -> dict[str, Any]:
        node = self.db.get(DocsNode, id_)
        if node is None or node.deleted_at is None:
            raise NotFoundError(f"回收站中无此节点：{id_}")
        # 父节点若也在回收站 → 拒绝（避免出现「挂在已删节点下的活节点」）
        if node.parent_id is not None:
            parent = self.db.get(DocsNode, node.parent_id)
            if parent is not None and parent.deleted_at is not None:
                raise ValidationError("父节点仍在回收站，请先恢复父节点")
        node.deleted_at = None
        self.db.add(node)
        self.db.commit()
        self.db.refresh(node)
        event_bus.publish("docs.node.restored", _dump_node(node), source="docs")
        return _dump_node(node)

    def hard_delete(self, id_: str) -> None:
        node = self.db.get(DocsNode, id_)
        if node is None or node.deleted_at is None:
            raise NotFoundError(f"回收站中无此节点：{id_}")
        # 先清子节点（递归），再清 content / revisions / fts
        children = self.db.exec(select(DocsNode).where(DocsNode.parent_id == id_)).all()
        for c in children:
            self.hard_delete(c.id)
        self.db.get(DocsContent, id_)
        content = self.db.get(DocsContent, id_)
        if content is not None:
            self.db.delete(content)
        for rev in self.db.exec(select(DocsRevision).where(DocsRevision.node_id == id_)).all():
            self.db.delete(rev)
        self._delete_fts(id_)
        self.db.delete(node)
        self.db.commit()

    # ───────────────────────── 版本历史 ─────────────────────────
    def save_content(self, id_: str, body: Any) -> dict[str, Any]:
        node = self.db.get(DocsNode, id_)
        if node is None or node.deleted_at is not None:
            raise NotFoundError(f"节点不存在：{id_}")
        if node.kind != "doc":
            raise ValidationError(f"只有 doc 节点能存正文，{id_} 是 {node.kind}")
        fmt = (body.format or "md").strip().lower()
        if fmt not in ("txt", "md"):
            raise ValidationError(f"format 只能是 txt|md，收到 {fmt!r}")
        content = self.db.get(DocsContent, id_)
        if content is None:
            content = DocsContent(node_id=id_, format=fmt, body=body.body)
        else:
            content.format = fmt
            content.body = body.body
            content.updated_at = utcnow()
        # 先写版本快照（保存即快照；回退也是走这里，历史不丢）
        rev = DocsRevision(node_id=id_, content=body.body, format=fmt)
        self.db.add(rev)
        self.db.add(content)
        self.db.commit()
        self.db.refresh(content)
        self._sync_fts(node, body.body)
        event_bus.publish("docs.node.updated", _dump_detail(node, content), source="docs")
        return _dump_detail(node, content)

    # ───────── 按路径写正文（2026-09-27 · 主人「补 docs.content.write」）─────────
    def _find_child(self, parent_id: str | None, name: str) -> DocsNode | None:
        """同层找同名**未删**节点；多个取第一个（按 sort, created_at）。"""
        stmt = (
            select(DocsNode)
            .where(
                col(DocsNode.parent_id) == parent_id,
                col(DocsNode.name) == name,
                col(DocsNode.deleted_at).is_(None),
            )
            .order_by(col(DocsNode.sort), col(DocsNode.created_at))
        )
        return self.db.exec(stmt).first()

    def _make_node(self, parent_id: str | None, name: str, kind: str) -> DocsNode:
        """建一个节点（与 create() 同语义：FTS + 事件都不落下）。"""
        node = DocsNode(parent_id=parent_id, kind=kind, name=name, sort=0, meta_json=None)
        self.db.add(node)
        self.db.commit()
        self.db.refresh(node)
        if kind == "doc":
            self._sync_fts(node, "")
        event_bus.publish("docs.node.created", _dump_node(node), source="docs")
        return node

    def upsert_content_by_path(self, body: Any) -> dict[str, Any]:
        """按路径写正文：逐段解析，缺则按需建（中段 folder / 末段 doc）。

        幂等：同一条路径重复写只更新正文（保存即快照，历史不丢），不会重复建节点。
        冲突不静默：中段撞上 doc / 末段撞上 folder -> 直接报错，绝不乱建。
        """
        raw = (body.path or "").strip()
        segments = [s.strip() for s in raw.split("/") if s.strip()]
        if not segments:
            raise ValidationError(f"path 无法定位（全是空段）：{raw!r}")

        parent_id: str | None = None
        node: DocsNode | None = None
        for idx, seg in enumerate(segments):
            last = idx == len(segments) - 1
            want = "doc" if last else "folder"
            node = self._find_child(parent_id, seg)
            if node is None:
                if not getattr(body, "create_if_missing", True):
                    raise NotFoundError(f"路径不存在：{raw}（缺 {seg!r}）")
                node = self._make_node(parent_id, seg, want)
            elif node.kind != want:
                raise ValidationError(
                    f"路径第 {idx + 1} 段 {seg!r} 是 {node.kind}，应为 {want}"
                )
            parent_id = node.id

        assert node is not None  # segments 非空 => 循环至少执行一次
        return self.save_content(node.id, body)

    def list_revisions(
        self, id_: str, limit: int = 50, cursor: str | None = None
    ) -> tuple[list[dict[str, Any]], str | None]:
        node = self.db.get(DocsNode, id_)
        if node is None or node.deleted_at is not None:
            raise NotFoundError(f"节点不存在：{id_}")
        rows, next_cursor = self._page_rows(
            DocsRevision,
            limit=limit,
            cursor=cursor,
            conditions=(DocsRevision.node_id == id_,),
            order_by=col(DocsRevision.created_at).desc(),
        )
        return [
            {
                "id": r.id,
                "node_id": r.node_id,
                "format": r.format,
                "created_at": r.created_at,
                "content": r.content,
            }
            for r in rows
        ], next_cursor

    def get_revision(self, id_: str, rev_id: str) -> dict[str, Any]:
        node = self.db.get(DocsNode, id_)
        if node is None or node.deleted_at is not None:
            raise NotFoundError(f"节点不存在：{id_}")
        rev = self.db.get(DocsRevision, rev_id)
        if rev is None or rev.node_id != id_:
            raise NotFoundError(f"版本不存在：{rev_id}")
        return {
            "id": rev.id,
            "node_id": rev.node_id,
            "format": rev.format,
            "content": rev.content,
            "created_at": rev.created_at,
        }

    def restore_revision(self, id_: str, rev_id: str) -> dict[str, Any]:
        rev = self.get_revision(id_, rev_id)
        return self.save_content(id_, _RevBody(format=rev["format"], body=rev["content"]))

    # ───────────────────────── 检索（FTS5） ─────────────────────────
    def search(
        self, q: str, limit: int = 50, cursor: str | None = None
    ) -> tuple[list[dict[str, Any]], str | None]:
        q = (q or "").strip()
        if not q:
            raise ValidationError("q 不能为空")
        # FTS5 MATCH：先转成「每个词 OR」的查询（trigram 对连续中文子串友好，英文走默认）
        terms = [t for t in q.replace('"', " ").split() if t]
        if not terms:
            raise ValidationError("q 无效")
        # ★ trigram 要求每个词 ≥3 字符；对 1-2 字符的词退化为 LIKE 匹配（标题/正文）
        #（bigram 在标准 SQLite 不可用，见迁移 0002 说明）
        short = [t for t in terms if len(t) < 3]
        long = [t for t in terms if len(t) >= 3]
        hit_ids: set[str] = set()
        if long:
            match_expr = " OR ".join(f'"{t}"' for t in long)
            hit_ids.update(
                row[0]
                for row in self.db.execute(
                    text("SELECT node_id FROM docs_fts WHERE docs_fts MATCH :q").bindparams(
                        q=match_expr
                    )
                ).all()
            )
        if short:
            like = "%" + "%".join(short) + "%"
            rows = self.db.exec(
                select(DocsNode).where(
                    col(DocsNode.deleted_at).is_(None),
                    (col(DocsNode.name).like(like)) | (col(DocsNode.meta_json).like(like)),
                )
            ).all()
            hit_ids.update(n.id for n in rows)
            # O2：短词也搜正文（标题优先靠 score）
            for t in short:
                plike = f"%{t}%"
                for (nid,) in self.db.execute(
                    text("SELECT node_id FROM docs_content WHERE body LIKE :like").bindparams(
                        like=plike
                    )
                ).all():
                    hit_ids.add(str(nid))
        if not hit_ids:
            return [], None
        rows, next_cursor = self._page_rows(
            DocsNode,
            limit=limit,
            cursor=cursor,
            conditions=(col(DocsNode.deleted_at).is_(None), col(DocsNode.id).in_(list(hit_ids))),
            order_by=col(DocsNode.updated_at).desc(),
        )
        out = []
        for r in rows:
            d = _dump_node(r)
            name = str(d.get("name") or "")
            content = self.db.get(DocsContent, r.id)
            body = (content.body if content else "") or ""
            score = 0.0
            for t in terms:
                if t.lower() in name.lower():
                    score += 3.0
                if t.lower() in body.lower():
                    score += 1.0
            hl_t = name
            hl_b = body[:160]
            for t in sorted(terms, key=len, reverse=True):
                if not t:
                    continue
                if t.lower() in hl_t.lower():
                    hl_t = hl_t.replace(t, f"[[{t}]]", 1) if t in hl_t else hl_t
                if t.lower() in hl_b.lower():
                    idx = hl_b.lower().find(t.lower())
                    if idx >= 0:
                        hl_b = hl_b[:idx] + f"[[{hl_b[idx:idx+len(t)]}]]" + hl_b[idx + len(t) :]
            d["score"] = score
            d["highlight"] = hl_b if "[[" in hl_b else hl_t
            d["title_highlight"] = hl_t
            out.append(d)
        out.sort(key=lambda x: (-float(x.get("score") or 0)))
        return out, next_cursor

    # ───────────────────────── FTS 同步（service 层维护） ─────────────────────────
    def _sync_fts(self, node: DocsNode, body: str | None = None) -> None:
        """同步 docs_fts：doc 节点 insert/update/delete。"""
        self._delete_fts(node.id)
        if node.kind != "doc" or node.deleted_at is not None:
            return
        if body is None:
            content = self.db.get(DocsContent, node.id)
            body = content.body if content else ""
        # FTS5 虚拟表的插入走普通 INSERT（node_id 是 UNINDEXED 列，rowid 自动生成）
        stmt = text("INSERT INTO docs_fts(node_id, title, body) VALUES (:id, :title, :body)")
        self.db.execute(stmt.bindparams(id=node.id, title=node.name, body=body))
        self.db.commit()

    def _delete_fts(self, node_id: str) -> None:
        """FTS5 虚拟表不能用 `WHERE node_id=...` 删（只认 MATCH / rowid），
        先查出该 node 的 rowid 再按 rowid 删。"""
        rows = self.db.execute(
            text("SELECT rowid FROM docs_fts WHERE node_id = :id").bindparams(id=node_id)
        ).all()
        for (rowid,) in rows:
            self.db.execute(text("DELETE FROM docs_fts WHERE rowid = :rid").bindparams(rid=rowid))
        self.db.commit()

    # ───────────────────────── 通用分页 ─────────────────────────
    def _page_rows(
        self,
        model: type[_T],
        *,
        limit: int,
        cursor: str | None,
        conditions: tuple[Any, ...] = (),
        order_by: Any | None = None,
    ) -> tuple[list[_T], str | None]:
        limit = min(max(limit, 1), 200)
        try:
            offset = decode_cursor(cursor) if cursor else 0
        except ValueError as ex:
            raise ValidationError(str(ex)) from ex
        stmt = select(model)
        for cond in conditions:
            stmt = stmt.where(cond)
        stmt = (
            stmt.order_by(order_by) if order_by is not None else stmt.order_by(model.id)  # type: ignore[attr-defined]
        )
        rows = self.db.exec(stmt.offset(offset).limit(limit + 1)).all()
        has_next = len(rows) > limit
        items = rows[:limit]
        next_cursor = encode_cursor(offset + limit) if has_next else None
        return list(items), next_cursor


class _RevBody:
    """轻量版本回退载体（对齐 DocsContentIn 形状）。"""

    def __init__(self, format: str, body: str) -> None:
        self.format = format
        self.body = body


def _is_descendant_of(r: DocsNode, anc: DocsNode, rows: list[DocsNode]) -> bool:
    """r 是否是 anc 的子孙（沿 parent_id 哈希向上爬）。"""
    by_id = {n.id: n for n in rows}
    cur: DocsNode | None = r
    while cur is not None and cur.parent_id is not None:
        parent = by_id.get(cur.parent_id)
        if parent is None:
            break
        if parent.id == anc.id:
            return True
        cur = parent
    return False


def _assemble(rows: list[DocsNode], root: str | None) -> list[dict[str, Any]]:
    """内存哈希组装：一次遍历成树。返回森林（root=None）或单棵子树（root=id）。"""
    by_id: dict[str, dict[str, Any]] = {}
    for n in rows:
        d = _dump_node(n)
        d["children"] = []
        by_id[n.id] = d
    roots: list[dict[str, Any]] = []
    for n in rows:
        d = by_id[n.id]
        if n.parent_id is not None and n.parent_id in by_id:
            by_id[n.parent_id]["children"].append(d)
        else:
            roots.append(d)

    def sort_tree(node: dict[str, Any]) -> None:
        node["children"].sort(key=lambda c: (c["sort"], c["name"], c["created_at"]))
        for c in node["children"]:
            sort_tree(c)

    for r in roots:
        sort_tree(r)
    roots.sort(key=lambda c: (c["sort"], c["name"], c["created_at"]))
    if root is not None:
        for r in roots:
            if r["id"] == root:
                return [r]
        return []
    return roots
