"""A2 finance 定时同步：默认关闭时的调度器行为测试（不触网、不写库）。"""
from __future__ import annotations

import os

os.environ.setdefault("DB_PATH", "./data/tmp_t_finance_sched.db")
os.environ.pop("FINANCE_SYNC_ENABLED", None)

from modules.finance.scheduler import (  # noqa: E402
    scheduler_status,
    start_scheduler,
    stop_scheduler,
)


def test_scheduler_disabled_by_default() -> None:
    stop_scheduler()
    assert start_scheduler() is False
    st = scheduler_status()
    assert st["enabled"] is False
    assert st["running"] is False


def test_scheduler_enabled_starts_once(monkeypatch) -> None:
    stop_scheduler()
    monkeypatch.setenv("FINANCE_SYNC_ENABLED", "true")
    monkeypatch.setenv("FINANCE_SYNC_INTERVAL_HOURS", "6")
    try:
        assert start_scheduler() is True
        # 第二次启动应幂等
        assert start_scheduler() is False
        st = scheduler_status()
        assert st["enabled"] is True
        assert st["running"] is True
    finally:
        stop_scheduler()
        monkeypatch.delenv("FINANCE_SYNC_ENABLED", raising=False)
    assert scheduler_status()["running"] is False
