"""内核配置（pydantic-settings 读取 .env）。

★ 铁律：任何真实密钥都不许写进代码，一律从这里读。
  必填项缺失时，启动要报**清晰**错误（指明缺哪个），不许静默回退默认值。
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录（services/api/core/config.py -> parents[3] == 项目根 life/）。
# 用来在 cwd 之外也能定位 .env（uvicorn / pytest 都在 services/api 下运行）。
_PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """所有运行时配置。

    必填（无默认值）：SECRET_KEY / ADMIN_PASSWORD_HASH / TOTP_SECRET。
    缺任何一个，pydantic 会在构造时抛 ValidationError，错误信息直接指出字段名。
    """

    model_config = SettingsConfigDict(
        # 优先 cwd 下的 .env，其次项目根的 .env（与 docker-compose 的 ../.env 一致）。
        env_file=[str(Path.cwd() / ".env"), str(_PROJECT_ROOT / ".env")],
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── 运行环境 ──
    app_env: str = Field(default="development")
    tz: str = Field(default="Asia/Shanghai")

    # ── 安全（必填）──
    secret_key: str = Field(
        ...,  # 必填：缺失即启动失败
        description="JWT 签名密钥，部署用 openssl rand -hex 32 生成",
    )
    jwt_access_minutes: int = Field(default=30)
    jwt_refresh_days: int = Field(default=14)
    admin_password_hash: str = Field(
        ...,  # 必填：单用户管理员密码的 argon2 哈希
        description="管理员密码 argon2 哈希，不存明文",
    )
    totp_secret: str = Field(
        ...,  # 必填：TOTP 二步密钥（base32）
        description="TOTP 二步验证密钥（base32）",
    )

    # ── 数据 ──
    db_path: str = Field(default="./data/lifos.db")
    backup_dir: str = Field(default="./data/backups")
    backup_keep_days: int = Field(default=30)

    # ── CORS ──
    cors_allow_origins: str = Field(default="*")

    # ── 日志 ──
    log_level: str = Field(default="INFO")
    log_dir: str = Field(default="./data/logs")

    # ── 限流 ──
    rate_limit_login_per_min: int = Field(default=5)
    rate_limit_general_per_min: int = Field(default=300)

    # ── 幂等缓存时长（小时，默认 24h）──
    idempotency_ttl_hours: int = Field(default=24)

    @property
    def cors_origins_list(self) -> list[str]:
        if self.cors_allow_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """全局唯一配置实例（带缓存）。

    构造失败（缺必填项）会向上抛出 pydantic ValidationError，
    由 create_app 捕获并转成清晰启动错误。
    """
    # 说明：三个安全字段声明为"必填"（`Field(...)`），但它们的值由 pydantic-settings
    # 在**运行时**从 .env / 环境变量注入，mypy 看不到这一层，因此这里对 call-arg 做一次
    # 定向忽略。这不是掩盖缺陷：真缺值时 pydantic 会在运行时报 ValidationError，
    # 由 create_app 捕获并转成清晰的启动错误。
    return Settings()  # type: ignore[call-arg]


def settings_as_dict() -> dict[str, Any]:
    """脱敏后的配置快照（用于 /readyz，绝不外泄密钥）。"""
    s = get_settings()
    return {
        "app_env": s.app_env,
        "tz": s.tz,
        "jwt_access_minutes": s.jwt_access_minutes,
        "jwt_refresh_days": s.jwt_refresh_days,
        "rate_limit_login_per_min": s.rate_limit_login_per_min,
        "rate_limit_general_per_min": s.rate_limit_general_per_min,
    }
