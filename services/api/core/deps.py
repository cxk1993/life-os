"""依赖注入：数据库会话 + 当前用户 + 作用域。

★ T04 未就绪：core 只依赖接口（Protocol），不 import db/。
  get_db 在没有引擎时明确报错（"数据库未就绪"），不许静默成功。
  T04 就绪后调用 set_engine(engine) 注入真实引擎即可，无需改其它代码。
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from sqlmodel import Session

from core.errors import ServiceUnavailableError
from core.security import get_current_user, require_scope

__all__ = [
    "get_db",
    "get_current_user",
    "require_scope",
    "set_engine",
    "DatabaseProvider",
]


@runtime_checkable
class DatabaseProvider(Protocol):
    """T04 提供的数据库引擎接口（最小形态）。"""

    def __call__(self) -> Session: ...  # 返回一个可用 Session


_engine_factory: Any = None


def set_engine(factory: Any) -> None:
    """T04 注入引擎工厂（callable -> Session）。core 自身不建引擎。"""
    global _engine_factory
    _engine_factory = factory


def get_db() -> Session:
    """依赖注入：返回数据库会话。

    开发期/测试期若 T04 尚未注入引擎，调用即报错（明确告知等待 T04），
    绝不会返回假连接掩盖故障。
    """
    if _engine_factory is None:
        raise ServiceUnavailableError(
            "数据库未就绪：等待 T04 注入引擎（core.deps.set_engine）"
        )
    return _engine_factory()
