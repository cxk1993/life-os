"""插件模型：笔记。

★ 表名必须以插件 id 为前缀（`notes_`），否则内核拒绝建表。
★ 时间列一律用 `db.base.TimestampTZ`（UTC 存储 + 往返保时区）。
★ Mixin 里的字段只能用 sa_type=（用 sa_column= 会在多表继承时抛
  "Column object ... already assigned to Table"）。
★ 笔记**全文不进服务器库**——只缓存索引；全文经 bridge 按需拉取。

表：
  note_lib    本机笔记夹登记（与 bridge config.yaml 的 lib 对应）
  note_index  笔记索引缓存（(lib_id, rel_path) 唯一定位一篇）
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Text as SAText
from sqlmodel import Field, UniqueConstraint

from db.base import PkMixin, TimestampMixin, TimestampTZ


class NoteLib(PkMixin, TimestampMixin, table=True):
    """一个本机笔记库（Obsidian vault / 文件夹）。"""

    __tablename__ = "note_lib"

    # 与 bridge config.yaml 里的 lib key 一致（如 main / review / undo）
    key: str = Field(max_length=64, index=True, unique=True)
    name: str = Field(default="", max_length=120)
    enabled: bool = Field(default=True, index=True)
    # 最近一次同步到的 md 数量
    md_count: int = Field(default=0)


class NoteIndex(PkMixin, TimestampMixin, table=True):
    """一篇笔记的索引缓存（无全文）。"""

    __tablename__ = "note_index"
    __table_args__ = (UniqueConstraint("lib_id", "rel_path", name="uq_note_lib_path"),)

    lib_id: str = Field(max_length=32, index=True, foreign_key="note_lib.id")
    rel_path: str = Field(max_length=500, index=True)  # POSIX 相对路径
    title: str = Field(default="", max_length=200, index=True)
    mtime: int = Field(default=0)  # 本机文件 mtime（unix 秒）
    size: int = Field(default=0)
    content_hash: str = Field(default="", max_length=64)
    excerpt: str = Field(default="", sa_type=SAText)
    # 最近一次成功同步进库的时间（UTC）
    synced_at: datetime | None = Field(default=None, sa_type=TimestampTZ)
