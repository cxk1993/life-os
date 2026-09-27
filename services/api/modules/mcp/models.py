"""插件模型：MCP Server（T18）。

★ 表名必须以插件 id 为前缀（`mcp_xxx`），否则内核拒绝建表。
★ 时间列一律用 `db.base.TimestampTZ`（UTC 存储 + 往返保时区）。
★ Mixin 里的字段只能用 sa_type=（用 sa_column= 会在多表继承时抛
  "Column object ... already assigned to Table"）。

PAT 安全红线（ADR-0003 §2.3）：
  - 只存 token_hash（SHA-256）与 token_prefix（展示用前 13 位）；
  - 明文只在创建响应里出现一次，之后任何地方（日志 / 审计 / 本表）都不再有。
"""
from __future__ import annotations

from datetime import datetime

from sqlmodel import Field

from db.base import PkMixin, TimestampMixin, TimestampTZ


class McpPat(PkMixin, TimestampMixin, table=True):
    """mcp_pat · MCP 客户端的 PAT（Personal Access Token）。

    AI 客户端拿 PAT 调 MCP 端点，与主人的登录 JWT 完全独立：
    可限 scope、可吊销、可过期、可审计。
    """

    __tablename__ = "mcp_pat"

    name: str = Field(default="", max_length=64, index=True)
    token_hash: str = Field(max_length=64, index=True, unique=True)
    # 明文前 13 位（如 lifmcp_a1b2c1），仅用于列表里辨认"哪个 PAT"，不参与鉴权。
    token_prefix: str = Field(max_length=24)
    # 逗号分隔，如 "calendar:write,notes:read"；空 = 无任何权限。
    # ★ 2026-09-27（云昔）：512 → 4096。schemas.py 的 scopes 上限已放宽到 1024 项，
    #   逗号串长度不再受 512 约束。SQLite 不强制 VARCHAR 长度 → 对现有库**零行为变更**，
    #   这里改的是"声明别自相矛盾"；4096 字符 ≈ 290 个 scope，远超实际（现 30 个）。
    scopes: str = Field(default="", max_length=4096)
    expires_at: datetime | None = Field(default=None, sa_type=TimestampTZ)
    last_used_at: datetime | None = Field(default=None, sa_type=TimestampTZ)
    revoked_at: datetime | None = Field(default=None, sa_type=TimestampTZ)
    revoked_by: str | None = Field(default=None, max_length=64)
