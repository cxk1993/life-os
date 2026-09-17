"""笔记出入参。

★ 出参不包 `{"code":0,"data":...}`，直接返回资源本身。
★ 全文只在 get 单篇时返回；列表只有索引（title / excerpt / path）。
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class LibOut(BaseModel):
    id: str
    key: str
    name: str
    enabled: bool
    md_count: int


class NoteBrief(BaseModel):
    id: str
    lib_id: str
    lib_key: str = ""
    rel_path: str
    title: str
    excerpt: str = ""
    mtime: int = 0
    size: int = 0
    synced_at: datetime | None = None


class NoteDetail(NoteBrief):
    content: str = ""


class SearchOut(BaseModel):
    items: list[NoteBrief] = []
    total: int = 0


class SyncResult(BaseModel):
    lib_key: str
    upserted: int = 0
    removed: int = 0
    md_count: int = 0


class LibCreate(BaseModel):
    key: str = Field(min_length=1, max_length=64)
    name: str = Field(default="", max_length=120)
    enabled: bool = True
