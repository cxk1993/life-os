"""TOTP_REQUIRED 开关测试（主人 2026-09-20 指示：两步验证暂时关闭，未来按需启用）。

不 mock 任何 auth 逻辑：用真实 AuthService + 真实 argon2 哈希 +
monkeypatch settings 的方式验证开关行为。
"""
from __future__ import annotations

import os

os.environ["DB_PATH"] = "./data/tmp_totp_switch.db"


import pytest  # noqa: E402

from core.config import get_settings  # noqa: E402
from core.errors import UnauthorizedError  # noqa: E402
from modules.auth import service as auth_service  # noqa: E402

PASSWORD = "REDACTED-test"


class _FakeSettings:
    """只暴露 AuthService.login 用到的字段，totp_required 可切换。"""

    def __init__(self, *, totp_required: bool) -> None:
        from argon2 import PasswordHasher

        self.admin_password_hash = PasswordHasher().hash(PASSWORD)
        self.totp_secret = "JBSWY3DPEHPK3PXP"
        self.totp_required = totp_required
        self.jwt_access_minutes = 30
        self.jwt_refresh_days = 14


@pytest.fixture()
def real_totp_code(monkeypatch: pytest.MonkeyPatch):
    """真 TOTP 密钥下的真实动态码（验证开关开启时路径不变）。"""
    import pyotp

    code = pyotp.TOTP("JBSWY3DPEHPK3PXP").now()
    monkeypatch.setattr(auth_service, "get_settings", lambda: _FakeSettings(totp_required=True))
    yield code


def test_totp_required_true_without_code_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_service, "get_settings", lambda: _FakeSettings(totp_required=True))
    with pytest.raises(UnauthorizedError):
        auth_service.AuthService().login(PASSWORD, "")


def test_totp_required_true_with_valid_code_ok(
    monkeypatch: pytest.MonkeyPatch, real_totp_code: str
) -> None:
    tokens = auth_service.AuthService().login(PASSWORD, real_totp_code)
    assert tokens["access"] and tokens["refresh"]


def test_totp_required_false_password_only_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """★ 主人指示的核心行为：开关关闭后，仅密码即可登录（totp 缺省为空）。"""
    monkeypatch.setattr(auth_service, "get_settings", lambda: _FakeSettings(totp_required=False))
    tokens = auth_service.AuthService().login(PASSWORD, "")
    assert tokens["access"] and tokens["refresh"]


def test_totp_required_false_wrong_password_still_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(auth_service, "get_settings", lambda: _FakeSettings(totp_required=False))
    with pytest.raises(UnauthorizedError):
        auth_service.AuthService().login("wrong-password", "")


def test_settings_has_totp_required_field() -> None:
    """真实 Settings 必须有 totp_required 字段（服务器 .env 经 TOTP_REQUIRED 控制）。"""
    s = get_settings()
    assert isinstance(s.totp_required, bool)
