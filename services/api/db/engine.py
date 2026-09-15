"""SQLite 引擎（T04 · 步骤 1）。

SQLite 正确配置（总纲雷区 #6）：
    PRAGMA journal_mode=WAL      # 读写并发，备份期间不阻塞
    PRAGMA busy_timeout=5000     # 写锁冲突时最多等 5 秒，不立刻抛 database is locked
    PRAGMA foreign_keys=ON       # SQLite 默认关闭外键，必须显式开
    PRAGMA synchronous=NORMAL    # WAL 模式推荐档位

★ 写并发策略（单用户系统的正确姿势）：
  1. SQLite 是单写者：同一时刻只允许一个写事务，WAL 让读不被写阻塞。
  2. busy_timeout=5000 把"撞锁"变成"排队"，10 并发以内实测够用（见 tests）。
  3. 业务层一律**短事务**：repo.py 的每个操作即开即收，禁止在请求中途
     长时间持有写事务（那是 database is locked 的真正来源）。
  4. 备份走 sqlite3 .backup API（在线备份），不锁主库。

注入方式（T03 约定）：core.deps.set_engine(工厂) —— core 不 import db，
由本模块在 init_engine() 里反向注册，入口只调 init_engine() 一行。
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Engine, make_url
from sqlmodel import Session, create_engine

from core.deps import set_engine

logger = logging.getLogger(__name__)

_engine: Engine | None = None


def _apply_sqlite_pragmas(target: Engine) -> None:
    """每个新连接都执行四条 PRAGMA（连接级设置，必须 per-connection）。"""

    @event.listens_for(target, "connect")
    def _set_pragma(dbapi_connection: Any, _record: Any) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA synchronous=NORMAL")
        finally:
            cursor.close()


def _resolve_db_path(raw: str) -> Path:
    """相对路径相对 services/api 解析（uvicorn / pytest 都在这里跑）。"""
    p = Path(raw)
    if not p.is_absolute():
        p = Path(__file__).resolve().parent.parent / p  # services/api/<raw>
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def make_engine(db_url: str | None = None) -> Engine:
    """创建一个配置齐全的 SQLite 引擎。

    db_url 缺省时取 core.config.Settings.db_path（.env 可覆盖）。
    测试可传 "sqlite:///<tmp>/x.db"，互不污染。
    """
    if db_url is None:
        from core.config import get_settings  # 延迟导入：避免无谓的必填校验

        path = _resolve_db_path(get_settings().db_path)
        db_url = f"sqlite:///{path.as_posix()}"
    make_url(db_url)  # 早点发现格式错误，别等到第一次连接
    engine = create_engine(
        db_url,
        echo=False,
        # SQLite + FastAPI 线程池：同一连接可能被不同线程先后使用
        connect_args={"check_same_thread": False},
    )
    _apply_sqlite_pragmas(engine)
    return engine


def session_factory() -> Session:
    """给 core.deps.set_engine 用的会话工厂（callable -> Session）。"""
    if _engine is None:
        raise RuntimeError("db.engine.init_engine() 尚未调用")
    return Session(_engine)


def get_engine() -> Engine:
    """已初始化的引擎；未初始化时报人话错误。"""
    if _engine is None:
        raise RuntimeError("数据库引擎未初始化：请先调用 db.engine.init_engine()")
    return _engine


def init_engine(db_url: str | None = None) -> Engine:
    """初始化引擎并注册到 core.deps（幂等；重复调用返回同一引擎）。

    这是 main.py 里唯一需要出现的 db 代码：
        from db.engine import init_engine
        init_engine()
    """
    global _engine
    if _engine is None:
        _engine = make_engine(db_url)
        set_engine(session_factory)
        logger.info("数据库引擎已就绪：%s", _engine.url)
    return _engine
