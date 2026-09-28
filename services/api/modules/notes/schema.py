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
    score: float = 0.0
    highlight: str = ""


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
    key: str = Field(
        min_length=1, max_length=64, description="库的短标识（如 main / work），**唯一**，后续路径里用它"
    )
    name: str = Field(default="", max_length=120, description="库的显示名（留空则用 key）")
    enabled: bool = Field(default=True, description="是否纳入同步与搜索")

class NoteCreate(BaseModel):
    lib_id: str = Field(description="所属库的 id")
    title: str = Field(default="", max_length=200, description="笔记标题")
    rel_path: str = Field(
        min_length=1, max_length=512, description="库内相对路径（如 课程/高数.md）—— 与库共同决定唯一性"
    )
    content: str = Field(default="", description="正文。⚠️ **经本机桥写入磁盘**，服务器库里只存索引")


class NoteUpdate(BaseModel):
    title: str | None = Field(default=None, description="改标题")
    content: str | None = Field(default=None, description="改正文（经本机桥落盘）")

class TreeNode(BaseModel):
    id: str
    title: str
    rel_path: str
    is_dir: bool
    children: list["TreeNode"] = []


class NoteTree(BaseModel):
    lib_id: str
    lib_key: str
    root: TreeNode
