"""PAT 鉴权（T18 · ADR-0003 §2.3）。

AI 客户端拿独立 PAT（`lifmcp_` 前缀）访问 MCP 端点，不用主人的登录 JWT：
  1. 前缀识别 → 2. SHA-256 哈希比对 → 3. 未吊销 / 未过期 → 4. scope 校验。

红线：明文只在 generate_pat() 返回的那一刻存在（随后写进创建响应一次），
落库只有哈希；绝不打日志、绝不进 audit 详情。
"""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session, select

from core.deps import get_db
from core.errors import ForbiddenError, NotFoundError, UnauthorizedError

from .models import McpPat

PAT_PREFIX = "lifmcp_"

# 前缀长度 = "lifmcp_" + 6 位指纹 = 13（列表展示用，不参与鉴权）。
_PREFIX_LEN = len(PAT_PREFIX) + 6

_BEARER = HTTPBearer(auto_error=False)


def hash_pat(plain: str) -> str:
    """SHA-256 十六进制。PAT 是高熵随机串，无需 argon2 那类慢哈希。"""
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()


def generate_pat() -> tuple[str, str, str]:
    """生成 (明文, 哈希, 展示前缀)。明文只经此返回一次。"""
    plain = PAT_PREFIX + secrets.token_urlsafe(24)
    return plain, hash_pat(plain), plain[:_PREFIX_LEN]


@dataclass
class PatContext:
    """通过鉴权的 PAT 上下文（tools/call 时做 scope 校验用）。"""

    id: str
    name: str
    token_prefix: str
    scopes: set[str] = field(default_factory=set)

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes


def require_pat(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_BEARER)],
    db: Annotated[Session, Depends(get_db)],
) -> PatContext:
    """FastAPI 依赖：校验 Bearer PAT，通过则返回上下文。

    失败语义（401/403 均为内核 problem+json）：
      - 无 Authorization / 非 PAT 前缀 → 401
      - 哈希对不上 / 已吊销 / 已过期 → 401（不区分细节，防枚举）
    """
    if creds is None or not creds.credentials:
        raise UnauthorizedError("缺少 Authorization: Bearer <PAT>")
    plain = creds.credentials
    if not plain.startswith(PAT_PREFIX):
        raise UnauthorizedError(
            f"MCP 端点只接受 PAT（{PAT_PREFIX}*）；用户 JWT 请走 /pats 管理接口"
        )
    row = db.exec(
        select(McpPat).where(McpPat.token_hash == hash_pat(plain))
    ).first()
    if row is None:
        raise UnauthorizedError("PAT 无效")
    now = datetime.now(UTC)
    if row.revoked_at is not None:
        raise UnauthorizedError("PAT 已吊销")
    if row.expires_at is not None and row.expires_at <= now:
        raise UnauthorizedError("PAT 已过期")
    # 顺手登记 last_used_at（成功鉴权即算"使用"）。失败不更新。
    row.last_used_at = now
    db.add(row)
    db.commit()
    return PatContext(
        id=row.id,
        name=row.name,
        token_prefix=row.token_prefix,
        scopes={s for s in (row.scopes or "").split(",") if s},
    )


def ensure_scope(pat: PatContext, scope: str) -> None:
    """tools/call 时的 scope 拦截。缺 → 403，写明缺哪个。"""
    if not pat.has_scope(scope):
        raise ForbiddenError(
            f"PAT「{pat.name}」（{pat.token_prefix}）缺少 scope：{scope}；"
            f"现有 scopes：{sorted(pat.scopes) or '（无）'}"
        )


def mark_pat_revoked(db: Session, pat_id: str, by: str) -> McpPat:
    """吊销：置 revoked_at 即失效（幂等：已吊销的再吊销无副作用）。"""
    row = db.get(McpPat, pat_id)
    if row is None:
        raise NotFoundError(f"PAT 不存在：{pat_id}")
    if row.revoked_at is None:
        row.revoked_at = datetime.now(UTC)
        row.revoked_by = by
        db.add(row)
        db.commit()
        db.refresh(row)
    return row
