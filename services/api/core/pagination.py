"""cursor 分页工具（API 规范 §1.4）。

?limit=50&cursor=<opaque>；响应含 next_cursor。
cursor 是不透明的 base64 偏移量，避免暴露内部 id。
"""
from __future__ import annotations

import base64
from typing import Any, TypeVar

T = TypeVar("T")


def encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(str(offset).encode("utf-8")).decode("ascii")


def decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        return int(base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8"))
    except Exception:
        return 0


def paginate(items: list[T], limit: int, cursor: str | None = None) -> dict[str, Any]:
    """对内存列表做 cursor 分页（轻量；插件有大数据量时请在 service 层用 SQL 分页）。"""
    offset = decode_cursor(cursor)
    page = items[offset : offset + limit]
    next_offset = offset + len(page)
    next_cursor = encode_cursor(next_offset) if next_offset < len(items) else None
    return {"items": page, "next_cursor": next_cursor, "limit": limit}
