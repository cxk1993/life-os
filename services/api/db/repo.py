"""通用仓储（T04 · 步骤 6）——所有插件复用，不许各自重写分页。

用法（插件 service 层）：
    repo = Repo(session, CalendarEvent)
    row = repo.get(id_)
    row, = repo.page(limit=50, cursor=...)   # (items, next_cursor)
    obj = repo.create(title="...")
    repo.update(id_, title="新标题")          # updated_at 自动刷新
    repo.delete(id_)                          # 硬删；软删用 soft_delete()

分页 cursor：base64(JSON {"o": 偏移量})，按 id 排序保证稳定。
空结果 / 最后一页 → next_cursor = None。
"""
from __future__ import annotations

import base64
import json
import zlib
from typing import Any, Generic, TypeVar

from sqlmodel import Session, SQLModel, select

from db.base import utcnow

T = TypeVar("T", bound=SQLModel)


def encode_cursor(offset: int) -> str:
    raw = json.dumps({"o": offset}).encode("utf-8")
    return base64.urlsafe_b64encode(zlib.compress(raw)).decode("ascii")


def decode_cursor(cursor: str) -> int:
    """无效 cursor 抛 ValueError，由路由层转 4xx——不静默当第一页。"""
    try:
        raw = zlib.decompress(base64.urlsafe_b64decode(cursor.encode("ascii")))
        offset = json.loads(raw)["o"]
        if not isinstance(offset, int) or offset < 0:
            raise ValueError
        return offset
    except Exception as ex:  # noqa: BLE001 —— 任何解析失败都按坏游标处理
        raise ValueError(f"无效的 cursor：{cursor[:32]}…") from ex


class Repo(Generic[T]):
    """单表通用仓储。禁止跨插件 join——那是硬规则 #8。"""

    def __init__(self, session: Session, model: type[T]) -> None:
        self.session = session
        self.model = model

    # ---------- 读 ----------
    def get(self, id_: str) -> T | None:
        return self.session.get(self.model, id_)

    def page(
        self,
        *,
        limit: int = 50,
        cursor: str | None = None,
        conditions: tuple[Any, ...] = (),
    ) -> tuple[list[T], str | None]:
        """cursor 分页。返回 (本页数据, 下一页 cursor 或 None)。

        limit 上限 200：防止一次拽全表（雷区 #13 的表亲）。
        """
        if limit < 1:
            raise ValueError("limit 必须 >= 1")
        limit = min(limit, 200)
        offset = decode_cursor(cursor) if cursor else 0

        stmt = select(self.model).order_by(self.model.id)  # type: ignore[attr-defined]
        for cond in conditions:
            stmt = stmt.where(cond)
        rows = self.session.exec(stmt.offset(offset).limit(limit + 1)).all()

        has_next = len(rows) > limit
        items = rows[:limit]
        next_cursor = encode_cursor(offset + limit) if has_next else None
        return list(items), next_cursor

    # ---------- 写 ----------
    def create(self, **fields: Any) -> T:
        obj = self.model(**fields)
        self.session.add(obj)
        self.session.commit()
        self.session.refresh(obj)
        return obj

    def update(self, id_: str, **fields: Any) -> T | None:
        obj = self.get(id_)
        if obj is None:
            return None
        for k, v in fields.items():
            setattr(obj, k, v)
        obj.updated_at = utcnow()  # before_flush 兜底，这里显式再设一次
        self.session.add(obj)
        self.session.commit()
        self.session.refresh(obj)
        return obj

    def delete(self, id_: str) -> bool:
        obj = self.get(id_)
        if obj is None:
            return False
        self.session.delete(obj)
        self.session.commit()
        return True

    def soft_delete(self, id_: str) -> bool:
        """仅当模型带 SoftDeleteMixin（有 deleted_at 字段）时可用。"""
        if not hasattr(self.model, "deleted_at"):
            raise TypeError(f"{self.model.__name__} 没有软删字段（未继承 SoftDeleteMixin）")
        obj = self.get(id_)
        if obj is None:
            return False
        obj.deleted_at = utcnow()
        self.session.add(obj)
        self.session.commit()
        return True
