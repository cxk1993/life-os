"""notify_policy（N2）+ trend（D1-二期）单元测试。"""
from __future__ import annotations

import os

os.environ["DB_PATH"] = "./data/tmp_notify_trend.db"

from datetime import datetime  # noqa: E402

from modules.calendar.notify_policy import NotifyPolicy, evaluate  # noqa: E402
from modules.health.trend import trend_alert  # noqa: E402


def test_lead_and_pass() -> None:
    d = evaluate(
        planned=datetime(2026, 9, 23, 10, 20),
        now=datetime(2026, 9, 23, 10, 0),
        sent_last_hour=0,
        sent_today=0,
    )
    assert d.send and d.fire_at.minute == 10


def test_quiet_hours() -> None:
    d = evaluate(
        planned=datetime(2026, 9, 23, 23, 30),
        now=datetime(2026, 9, 23, 23, 30),
        sent_last_hour=0,
        sent_today=0,
    )
    assert not d.send and d.suppress_reason == "quiet_hours"


def test_rate_limited() -> None:
    d = evaluate(
        planned=datetime(2026, 9, 23, 10, 0),
        now=datetime(2026, 9, 23, 10, 0),
        sent_last_hour=3,
        sent_today=3,
    )
    assert not d.send and d.suppress_reason == "rate_limited"


def test_trend_streak_and_gte() -> None:
    assert trend_alert([]).should_alert is False
    assert trend_alert([3, 3, 3]).should_alert is False
    a = trend_alert([1, 2, 3])
    assert a.reason_code == "severity_streak_up:3" and a.level == "rest"
    b = trend_alert([2, 5])
    assert b.level == "see_doctor"
