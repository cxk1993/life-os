"""auth 业务逻辑：密码 + TOTP -> JWT。单用户，凭据来自配置（不落 db）。

★ T04 未就绪时，auth 直接读 core.config 中的管理员凭据，
  不依赖 db/，因此登录全流程现在就能真实跑通。
"""
from __future__ import annotations

from typing import Any

from core.config import get_settings
from core.errors import UnauthorizedError
from core.security import (
    USER_SUB,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
    verify_totp,
)


class AuthService:
    def login(self, password: str, totp: str, username: str | None = None) -> dict[str, str]:
        if username and username != USER_SUB:
            raise UnauthorizedError("未知用户")
        s = get_settings()
        if not verify_password(password, s.admin_password_hash):
            raise UnauthorizedError("密码错误")
        if not verify_totp(s.totp_secret, totp):
            raise UnauthorizedError("TOTP 校验失败")
        return {
            "access": create_access_token(USER_SUB),
            "refresh": create_refresh_token(USER_SUB),
        }

    def refresh(self, refresh_token: str) -> str:
        payload = decode_token(refresh_token, expected_type="refresh")
        return create_access_token(payload.get("sub", USER_SUB))

    def user_info(self, sub: str) -> dict[str, Any]:
        return {"sub": sub, "scopes": []}
