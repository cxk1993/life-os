"""鉴权：argon2 密码 + TOTP 二步 + JWT 签发/校验 + 依赖注入。

单用户系统：用户即管理员（sub="admin"）。
JWT：access 30min / refresh 14d；refresh 走 httpOnly Cookie（由 router 设置）。
★ 任何密钥都从 core.config 读，绝不硬编码。
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import jwt
import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from core.config import get_settings
from core.errors import UnauthorizedError

_HASHER = PasswordHasher()
_BEARER = HTTPBearer(auto_error=False)

ALGO = "HS256"
USER_SUB = "admin"


class User(BaseModel):
    sub: str
    scopes: list[str] = []


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _HASHER.verify(hashed, plain)
    except VerifyMismatchError:
        return False
    except Exception:
        # 哈希格式损坏等异常一律按失败（不许误判通过）
        return False


def verify_totp(secret: str, code: str) -> bool:
    if not secret or not code:
        return False
    try:
        return pyotp.TOTP(secret).verify(code, valid_window=1)
    except Exception:
        return False


def create_token(sub: str, token_type: str, expires_delta: timedelta) -> str:
    s = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": sub,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        "jti": __import__("uuid").uuid4().hex,
    }
    return jwt.encode(payload, s.secret_key, algorithm=ALGO)


def decode_token(token: str, expected_type: str | None = None) -> dict[str, Any]:
    s = get_settings()
    try:
        payload = jwt.decode(token, s.secret_key, algorithms=[ALGO])
    except jwt.PyJWTError as exc:
        raise UnauthorizedError(f"令牌无效：{exc}") from exc
    if expected_type and payload.get("type") != expected_type:
        raise UnauthorizedError("令牌类型不匹配")
    return payload


def create_access_token(sub: str) -> str:
    s = get_settings()
    return create_token(sub, "access", timedelta(minutes=s.jwt_access_minutes))


def create_refresh_token(sub: str) -> str:
    s = get_settings()
    return create_token(sub, "refresh", timedelta(days=s.jwt_refresh_days))


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_BEARER),  # noqa: B008
) -> User:
    """Bearer 依赖注入：无令牌 / 令牌无效 -> 401（RFC7807 由异常处理器转）。"""
    if creds is None or not creds.credentials:
        raise UnauthorizedError("缺少 Authorization: Bearer <token>")
    payload = decode_token(creds.credentials, expected_type="access")
    return User(sub=payload.get("sub", USER_SUB), scopes=[])


async def get_optional_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_BEARER),  # noqa: B008
) -> User | None:
    """可选 Bearer 依赖注入（ISSUE-011 案 C）：无令牌 -> None；令牌无效 -> 401。

    用途：公开面端点（如 /api/v1/modules 裸调只见精简字段）在无令牌时
    走 public 面，持有效令牌时走 full 面；**令牌无效/过期仍 401**
    （与 /api/v1/plugins 口径对齐，避免「假 token 反而少信息」的怪行为）。
    """
    if creds is None or not creds.credentials:
        return None
    payload = decode_token(creds.credentials, expected_type="access")
    return User(sub=payload.get("sub", USER_SUB), scopes=[])


# ── SSE 入场券（F2 加固：事件流不再裸奔）───────────────────────────────
# 为什么需要：浏览器原生 EventSource **不能带自定义 header**，所以 SSE 的鉴权
# 只能走 query；而直接把 access token 塞进 URL 会进浏览器历史 / 代理日志 /
# Referer —— 故改用「短时 + 类型隔离」的入场券，由已鉴权的 HTTP 端点换取。
SSE_TICKET_TTL_SECONDS = 60


def create_sse_ticket(sub: str) -> str:
    """签发 SSE 入场券（60 秒、type=sse，与 access/refresh 类型隔离，不可互换）。"""
    return create_token(sub, "sse", timedelta(seconds=SSE_TICKET_TTL_SECONDS))


def decode_sse_ticket(token: str) -> dict[str, Any]:
    """校验 SSE 入场券；无效 / 过期 / 类型不对 → 401。"""
    return decode_token(token, expected_type="sse")


def require_scope(scope: str) -> Callable[..., Any]:
    """作用域依赖工厂（单用户系统默认放通；保留接口给插件鉴权）。"""

    async def _dep(user: Annotated[User, Depends(get_current_user)]) -> User:  # noqa: B008
        if scope and scope not in user.scopes:
            # 当前单用户无 scope 体系，除显式要求外一律放通
            pass
        return user

    return _dep
