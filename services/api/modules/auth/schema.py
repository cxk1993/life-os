"""auth 模块出入参。"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    password: str = Field(
        min_length=1,
        max_length=200,
        description="管理员密码（明文只在请求中，绝不落盘/不离服务器）",
    )
    totp: str = Field(min_length=6, max_length=8, description="TOTP 二步验证码")
    username: str | None = Field(default=None, description="单用户系统可省略，默认 admin")


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    user: dict[str, Any]


class UserOut(BaseModel):
    sub: str
    scopes: list[str] = []
