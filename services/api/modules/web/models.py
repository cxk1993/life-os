"""插件模型：web_entry（网页条目 = 能力条目的输入端）。

★ 表名以插件 id 为前缀（web_）。
★ 时间列一律用 db.base.TimestampTZ（UTC 存储 + 往返保时区）。
★ Mixin 里的字段只能用 sa_type=（用 sa_column= 会在多表继承时抛
  "Column object ... already assigned to Table"）。

字段设计（★ 与 T20 能力目录共享的「能力条目」形状）：
  slug          人类可读 id（如 "example-portal"），唯一；agent 好认
  title         展示名（如 "理财"）
  url           要内嵌的地址，**只允许 http / https**
  icon          图标名（取允许的图标集），不是图片
  order         排序权重（小的在前）
  enabled       ★ 独立开关：关掉即从可用列表消失，但定义保留
  kind          web | web+rest | web+mcp
  endpoint      能力端点（kind != web 时必填）
  auth_ref      ★ 只存引用："none" 或 "<pat|bearer|basic>:env:<大写变量名>"
                —— 绝不存明文凭据（见 schema.validate_auth_ref）
  capabilities  能力清单（JSON 数组字符串；可留空，允许 agent 自探索）
  note          给 agent 的提示

★ 本模块**不出现任何具体站点名**（判据：插件不认识业务）。
  任何外部服务（记账、笔记、复盘…）都只是 web_entry 里的一行数据。
"""

from __future__ import annotations

import json

from sqlmodel import Field

from db.base import PkMixin, TimestampMixin


class WebEntry(PkMixin, TimestampMixin, table=True):
    """一个网页入口 —— 同时是"能力条目"的输入端（T20 能力目录的出口在它之上）。"""

    __tablename__ = "web_entry"

    slug: str = Field(max_length=64, unique=True, index=True)
    title: str = Field(max_length=120, index=True)
    url: str = Field(max_length=2000)
    icon: str | None = Field(default=None, max_length=40)
    order: int = Field(default=0, index=True)
    enabled: bool = Field(default=True, index=True)
    kind: str = Field(default="web", max_length=16)  # web | web+rest | web+mcp
    endpoint: str | None = Field(default=None, max_length=2000)
    auth_ref: str | None = Field(default=None, max_length=200)
    capabilities: str | None = Field(default=None)  # JSON 数组字符串
    note: str | None = Field(default=None, max_length=1000)


def caps_from_json(raw: str | None) -> list[str]:
    """DB 里的 capabilities 字符串 → 列表（空/非法 → []）。"""
    if not raw:
        return []
    try:
        val = json.loads(raw)
        return [str(c) for c in val] if isinstance(val, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def caps_to_json(caps: list[str] | None) -> str | None:
    """列表 → DB 字符串（空 → None，不占空间）。"""
    if not caps:
        return None
    return json.dumps([str(c) for c in caps], ensure_ascii=False)
