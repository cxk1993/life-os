"""web 出入参定义 + ★ 本卡最重要的三处校验。

★ 出参直接返回资源本身，不包 {code,data}。
★ 表名/字段名与 T20 能力目录**共享同一份形状**（见 CapabilityEntry）——
  两卡是"同一份数据的输入端与输出端"，字段名不得各写一套。

三处校验（都必须在**后端**做，前端只是第一道）：
  1. url：只允许 http / https（拒 javascript: / data: …）
  2. auth_ref：只允许 "none" 或 "<pat|bearer|basic|token>:env:<大写变量名>"；
     ★ 形状不符一律 400 —— 这是"绝不存明文凭据"的执行点
  3. kind：枚举 web | web+rest | web+mcp；非 web 时 endpoint 必填
"""

from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from core.errors import ValidationError

# ───────────────────────── 常量与正则 ─────────────────────────

KINDS = ("web", "web+rest", "web+mcp")

# slug：小写字母开头，允许小写字母/数字/连字符，2~64 位
_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{1,63}$")

# auth_ref：方式 + env 引用；变量名必须是大写字母开头的 SNAKE_CASE
_AUTH_REF_RE = re.compile(r"^(pat|bearer|basic|token):env:[A-Z][A-Z0-9_]{0,63}$")

# 疑似明文凭据：一段 24 位以上的连续 [A-Za-z0-9_-]（正常变量名/URL 不会这么长且无分隔）
_SECRET_LIKE_RE = re.compile(r"[A-Za-z0-9_\-]{24,}")


# ───────────────────────── 校验函数（service / schema 共用） ─────────────────────────


def normalize_url(raw: str) -> str:
    """校验并规范化内嵌地址。★ 只允许 http / https。"""
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
    """校验并规范化凭据引用。

    ★ 合法输入只有两类：空 / "none" / "<方式>:env:<大写变量名>"。
    ★ 其余一律拒绝 —— 尤其是"直接把 token 贴进来"。
    """
    if raw is None:
        return None
    value = raw.strip()
    if not value or value.lower() == "none":
        return None if not value else "none"
    if _AUTH_REF_RE.match(value):
        return value
    if _SECRET_LIKE_RE.search(value):
        raise ValidationError(
            "auth_ref 疑似含明文凭据。请只写引用形式，如 'pat:env:YOUR_TOKEN_VAR'；"
            "凭据本身请放 .env（已 gitignore），不要写进条目。"
        )
    raise ValidationError(
        "auth_ref 只接受 'none' 或 '<pat|bearer|basic>:env:<大写变量名>'"
        "（例：pat:env:EXAMPLE_TOKEN）"
    )


def normalize_kind(raw: str | None) -> str:
    """★ 缺省（None）→ "web"；**显式空串要拒**（多半是填漏了，不是想用默认值）。"""
    value = (raw if raw is not None else "web").strip()
    if value not in KINDS:
        raise ValidationError(f"kind 只允许 {' / '.join(KINDS)}（收到 {value!r}）")
    return value


def normalize_slug(raw: str) -> str:
    value = (raw or "").strip().lower()
    if not _SLUG_RE.match(value):
        raise ValidationError("slug 需为 2~64 位小写字母/数字/连字符，且以字母开头")
    return value


# ───────────────────────── ★ 与 T20 共享的能力条目形状 ─────────────────────────


class CapabilityEntry(BaseModel):
    """★ 能力目录（T20）消费的条目形状 —— 本卡只负责产出 `source="web_entry"` 的那批。

    字段名与 T20 的 catalog entry **必须一致**。改这里要同步 T20。
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
    source: str = "web_entry"  # web_entry | plugin | kernel | manual（T20 特批追加 manual）


# ───────────────────────── 出参 ─────────────────────────


class WebEntryOut(BaseModel):
    id: str
    slug: str
    title: str
    url: str
    icon: str | None = None
    order: int = 0
    enabled: bool = True
    kind: str = "web"
    endpoint: str | None = None
    auth_ref: str | None = None
    capabilities: list[str] = []
    note: str | None = None
    created_at: datetime
    updated_at: datetime
    # ★ 该条目进入 catalog 时的形状（只读预览；前端直接展示，不在前端重复拼装）
    capability: CapabilityEntry | None = None


class WebEntryListOut(BaseModel):
    items: list[WebEntryOut] = []
    total: int = 0


# ───────────────────────── 入参 ─────────────────────────


class WebEntryCreate(BaseModel):
    slug: str = Field(
        description="人类可读 id，如 example-portal。**建议唯一** —— 它会出现在 URL 里"
    )
    title: str = Field(max_length=120, description="入口显示名（≤120 字）")
    url: str = Field(description="要打开的网页地址，http / https")
    icon: str | None = Field(default=None, max_length=40, description="图标（可选）")
    order: int = Field(default=0, description="排序权重（越小越靠前）")
    enabled: bool = Field(default=True, description="是否启用")
    kind: str = Field(default="web", description="入口类型：web=普通网页 · capability=能力条目")
    endpoint: str | None = Field(default=None, description="接口地址（若这个入口其实是 API/MCP 能力）")
    auth_ref: str | None = Field(
        default=None, description="凭据引用：'none' 或 'pat:env:VAR' —— **只存引用名，不存明文**"
    )
    capabilities: list[str] = Field(default_factory=list, description="该入口声明提供的能力清单")
    note: str | None = Field(default=None, max_length=1000, description="备注（人话说明）")


class WebEntryUpdate(BaseModel):
    """全部可选：只改传了的字段（None 表示"不改"，不是"清空"）。"""

    title: str | None = Field(default=None, max_length=120, description="改显示名")
    url: str | None = Field(default=None, description="改网页地址（http/https）")
    icon: str | None = Field(default=None, max_length=40, description="改图标")
    order: int | None = Field(default=None, description="改排序权重")
    enabled: bool | None = Field(default=None, description="启用 / 停用")
    kind: str | None = Field(default=None, description="改入口类型：web | capability")
    endpoint: str | None = Field(default=None, description="改接口地址")
    auth_ref: str | None = Field(default=None, description="改凭据引用（**只存引用名，不存明文**）")
    capabilities: list[str] | None = Field(
        default=None, description="**整组替换**能力清单（不是追加）——要保留原来的请连原来的一起传"
    )
    note: str | None = Field(default=None, max_length=1000, description="改备注")


class TouchOut(BaseModel):
    id: str
    opened_at: datetime

class FrameUrlOut(BaseModel):
    """iframe 内嵌用的真实 URL（含 auth_ref 解析后的凭据）。

    ★ 条目表永不明文凭据：auth_ref 形如 "pat:env:PI_TOKEN"，运行时从 os.environ 取。
    ★ 解析失败（env 变量缺失）→ 422 + 错误详情，不吞异常。
    ★ 无 auth_ref 或 "none" → 直接返回原 url。
    """
    id: str
    slug: str
    title: str
    url: str  # 解析后的真实 URL（含凭据 query 参数）
    auth_ref: str | None = None  # 原始引用（用于前端展示）
    parsed: bool = True  # 是否成功解析凭据
