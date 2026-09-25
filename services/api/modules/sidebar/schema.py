"""TX-SIDEBAR-02 出入参 + href 白名单。"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

TYPES = ("link", "note", "announcement", "friend-link")
_LINKISH = ("link", "friend-link")


def href_allowed(url: str) -> bool:
    """只许 http(s) 绝对 URL。测试向量见契约 v0.1 §2.2。"""
    if not url:
        return False
    u = url.strip()
    low = u.lower()
    if low.startswith("//"):
        return False
    if not (low.startswith("http://") or low.startswith("https://")):
        return False
    return len(u) > len("https://")


class ItemOut(BaseModel):
    id: str
    type: str
    label: str
    icon: str = ""
    abbr: str = ""
    href: str = ""
    target: str = "_blank"
    body: str = ""
    node_ref: str = ""
    description: str = ""
    group: str = ""
    order: int = 0
    enabled: bool = True
    pinned: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ItemCreate(BaseModel):
    type: str = Field(default="link")
    label: str = Field(min_length=1, max_length=40)
    icon: str = Field(default="", max_length=80)
    abbr: str = Field(default="", max_length=4)
    href: str = Field(default="", max_length=500)
    target: str = Field(default="_blank", max_length=10)
    body: str = Field(default="", max_length=2000)
    node_ref: str = Field(default="", max_length=300)
    description: str = Field(default="", max_length=120)
    group: str = Field(default="", max_length=40)
    order: int = 0
    enabled: bool = True
    pinned: bool = False

    @field_validator("type")
    @classmethod
    def _vt(cls, v: str) -> str:
        if v not in TYPES:
            raise ValueError(f"type must be one of {TYPES}")
        return v

    @field_validator("href")
    @classmethod
    def _vh(cls, v: str, info) -> str:  # noqa: ANN001
        t = (info.data or {}).get("type", "link")
        if t in _LINKISH:
            if not href_allowed(v):
                raise ValueError("href must be absolute http(s) URL")
        elif v and not href_allowed(v):
            raise ValueError("href must be absolute http(s) URL when set")
        return v.strip()

    @field_validator("body")
    @classmethod
    def _vb(cls, v: str) -> str:
        # 契约 v0.2：正文一律走 notes/diary node_ref，本表不收 body。
        if v:
            raise ValueError("body rejected (use node_ref)")
        return v


class ItemUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=40)
    icon: str | None = None
    abbr: str | None = None
    href: str | None = None
    target: str | None = None
    body: str | None = None
    node_ref: str | None = None
    description: str | None = None
    group: str | None = None
    order: int | None = None
    enabled: bool | None = None
    pinned: bool | None = None

    @field_validator("href")
    @classmethod
    def _vh(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if v and not href_allowed(v):
            raise ValueError("href must be absolute http(s) URL")
        return v.strip()


class ListOut(BaseModel):
    items: list[ItemOut]
    count: int


class ReorderIn(BaseModel):
    ids: list[str]
