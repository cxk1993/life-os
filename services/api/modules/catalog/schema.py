"""能力目录出入参定义。

★ 与 T19 的 CapabilityEntry **共享同一份字段名形状**（测试锁 dead fields 集合）。
  插件之间不许 import，所以这里自建同名字段模型（不是复制代码，是复制形状）。
★ manual 条目的校验对齐 T19：url 只收 http/https、auth_ref 只收引用形式、kind 枚举。
★ 出参直接返回资源 JSON，不包 {code,data}；错误走 core.errors 由内核统一转 RFC7807。
"""
from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from core.errors import ValidationError

# ───────────────────────── 校验（对齐 T19，不 import） ─────────────────────────

KINDS = ("web", "web+rest", "web+mcp")

_AUTH_REF_RE = re.compile(r"^(pat|bearer|basic):env:[A-Z][A-Z0-9_]{0,63}$")
_SECRET_LIKE_RE = re.compile(r"[A-Za-z0-9_\-]{24,}")


def normalize_url(raw: str) -> str:
    value = (raw or "").strip()
    if not value:
        raise ValidationError("url 不能为空")
    parsed = urlparse(value)
    if parsed.scheme.lower() not in ("http", "https"):
        raise ValidationError(f"url 只允许 http / https（收到 scheme={parsed.scheme or '空'}）")
    if not parsed.netloc:
        raise ValidationError("url 缺少主机名")
    return value


def normalize_auth_ref(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = raw.strip()
    if not value or value.lower() == "none":
        return None if not value else "none"
    if _AUTH_REF_RE.match(value):
        return value
    if _SECRET_LIKE_RE.search(value):
        raise ValidationError(
            "auth_ref 疑似含明文凭据。请只写引用形式，如 'pat:env:YOUR_TOKEN_VAR'"
        )
    raise ValidationError(
        "auth_ref 只接受 'none' 或 "
        "'<pat|bearer|basic>:env:<大写变量名>'（例：pat:env:EXAMPLE_TOKEN）"
    )


def normalize_kind(raw: str | None) -> str:
    value = (raw if raw is not None else "web").strip()
    if value not in KINDS:
        raise ValidationError(f"kind 只允许 {' / '.join(KINDS)}（收到 {value!r}）")
    return value


# ───────────────────────── ★ 与 T19 共享的能力条目形状 ─────────────────────────


class CapabilityEntryOut(BaseModel):
    """★ 目录条目形状 —— 与 T19 的 CapabilityEntry 字段名**完全一致**。

    测试 `test_capability_shape_matches_t20` 锁的是字段名集合；本模型与
    web/schema.py 的 CapabilityEntry 字段名逐一对齐（不 import，形状同源）。
    """

    id: str
    name: str
    kind: str
    url: str | None = None
    endpoint: str | None = None
    auth_ref: str | None = None
    capabilities: list[str] = []
    enabled: bool = True
    note: str | None = None
    source: str = "manual"  # plugin | web_entry | kernel | manual


class CatalogOut(BaseModel):
    entries: list[CapabilityEntryOut] = []
    generatedAt: datetime
    counts: dict[str, int] = {}


# ───────────────────────── manual 入参 ─────────────────────────


class ManualEntryCreate(BaseModel):
    name: str = Field(max_length=120)
    kind: str = "web"
    url: str | None = None
    endpoint: str | None = None
    auth_ref: str | None = Field(default=None, description="'none' 或 'pat:env:VAR'")
    capabilities: list[str] = []
    note: str | None = Field(default=None, max_length=1000)
    catalog_id: str | None = Field(default=None, max_length=64, description="留空自动生成")
    enabled: bool = True


class ManualEntryUpdate(BaseModel):
    """全部可选：只改传了的字段（None 表示「不改」，不是「清空」）。"""

    name: str | None = Field(default=None, max_length=120)
    kind: str | None = None
    url: str | None = None
    endpoint: str | None = None
    auth_ref: str | None = None
    capabilities: list[str] | None = None
    note: str | None = Field(default=None, max_length=1000)
    enabled: bool | None = None