"""auth 路由层（薄：只做参数校验与调用 service）。

★ 不写 prefix=：内核按 manifest.api.base 自动挂 /api/v1/auth。
★ 不自己捕获异常：内核统一转 RFC7807。
"""
from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, Response

from core.config import get_settings
from core.deps import get_current_user
from core.errors import UnauthorizedError
from core.events import event_bus
from core.security import USER_SUB, User

from .schema import LoginIn, TokenOut, UserOut
from .service import AuthService

router = APIRouter()

REFRESH_COOKIE = "lifos_refresh"


def _cookie_secure() -> bool:
    return get_settings().app_env == "production"


@router.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, response: Response) -> TokenOut:
    tokens = AuthService().login(body.password, body.totp, body.username)
    # refresh 走 httpOnly Cookie（不进 JS，防 XSS 窃取）
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=tokens["refresh"],
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
        path="/api/v1/auth",
        max_age=get_settings().jwt_refresh_days * 86400,
    )
    event_bus.publish("auth.login", {"sub": USER_SUB}, source="auth")
    return TokenOut(
        access_token=tokens["access"],
        expires_in=get_settings().jwt_access_minutes * 60,
        user={"sub": USER_SUB},
    )


@router.post("/refresh", response_model=TokenOut)
def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
) -> TokenOut:
    if not refresh_token:
        raise UnauthorizedError("缺少 refresh token（Cookie）")
    access = AuthService().refresh(refresh_token)
    # 刷新后顺便续期 refresh cookie
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=refresh_token,
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
        path="/api/v1/auth",
        max_age=get_settings().jwt_refresh_days * 86400,
    )
    return TokenOut(
        access_token=access,
        expires_in=get_settings().jwt_access_minutes * 60,
        user={"sub": USER_SUB},
    )


@router.post("/logout")
def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie(REFRESH_COOKIE, path="/api/v1/auth")
    event_bus.publish("auth.logout", {"sub": USER_SUB}, source="auth")
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:  # noqa: B008
    info = AuthService().user_info(user.sub)
    return UserOut(sub=info["sub"], scopes=info.get("scopes", []))
