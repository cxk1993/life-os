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
    type: str = Field(
        default="link",
        description="项的类型：link=外链 · note=笔记 · announcement=公告 · friend-link=友情链接",
    )
    label: str = Field(min_length=1, max_length=40, description="侧栏显示的文字（≤40 字）")
    icon: str = Field(default="", max_length=80, description="图标（名或 URL，≤80 字）")
    abbr: str = Field(default="", max_length=4, description="图标下方的缩写小字（≤4 字）")
    href: str = Field(
        default="", max_length=500,
        description="跳转地址。**必须是绝对 http(s) URL**（白名单，拒 // 与非 http(s) 前缀）；仅 link / friend-link 必填",
    )
    target: str = Field(default="_blank", max_length=10, description="打开方式：_blank=新标签页 · _self=当前页")
    body: str = Field(
        default="", max_length=2000,
        description="⚠️ **本字段一律不收** —— 正文请改用 `node_ref` 指向笔记/日记节点",
    )
    node_ref: str = Field(default="", max_length=300, description="正文入口：指向 notes/diary 的节点引用")
    description: str = Field(default="", max_length=120, description="一句话说明（鼠标悬停/无障碍用）")
    group: str = Field(default="", max_length=40, description="分组名（同组项在侧栏里聚在一起）")
    order: int = Field(default=0, description="排序权重（越小越靠前）")
    enabled: bool = Field(default=True, description="是否启用")
    pinned: bool = Field(default=False, description="是否置顶（置顶项排在分组之前）")

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
    label: str | None = Field(default=None, min_length=1, max_length=40, description="改显示文字")
    icon: str | None = Field(default=None, description="改图标")
    abbr: str | None = Field(default=None, description="改缩写小字")
    href: str | None = Field(
        default=None, description="改跳转地址；仍必须是**绝对 http(s) URL**"
    )
    target: str | None = Field(default=None, description="改打开方式")
    body: str | None = Field(default=None, description="⚠️ 不收（用 node_ref）")
    node_ref: str | None = Field(default=None, description="改正文入口")
    description: str | None = Field(default=None, description="改说明")
    group: str | None = Field(default=None, description="改分组")
    order: int | None = Field(default=None, description="改排序权重")
    enabled: bool | None = Field(default=None, description="启用 / 停用")
    pinned: bool | None = Field(default=None, description="置顶 / 取消置顶")

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
