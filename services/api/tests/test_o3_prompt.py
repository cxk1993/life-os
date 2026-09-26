"""O3 习惯锚点提示测试。"""
from __future__ import annotations

import os

os.environ["DB_PATH"] = "./data/tmp_o3_prompt.db"

from datetime import UTC, date, datetime  # noqa: E402

from modules.calendar.notify_policy import NotifyPolicy, QuietHours, Timing  # noqa: E402
from modules.habits.prompt import evaluate_habit_prompt, parse_prompt, planned_fire  # noqa: E402


def test_parse_and_weekday_gate() -> None:
    p = parse_prompt({"anchor": "at_time", "at": "07:30", "days": [0], "message": "喝水"})
    assert p is not None
    # 2026-09-21=Mon(0) · 22=Tue(1) · 23=Wed(2)
    assert planned_fire(p, date(2026, 9, 21)) is not None
    assert planned_fire(p, date(2026, 9, 22)) is None
    assert planned_fire(p, date(2026, 9, 23)) is None


def test_quiet_and_open() -> None:
    p = parse_prompt({"anchor": "at_time", "at": "10:00", "days": list(range(7)), "message": "早"})
    policy = NotifyPolicy(quiet=QuietHours(start=datetime(2026, 1, 1, 23).time(), end=datetime(2026, 1, 1, 7, 30).time()), timing=Timing(lead_minutes=0))
    # ★ 2026-09-26 更新（astrbot）：静默判断已统一换算到 Asia/Shanghai（原先直接用
    #   now.time() 比钟面，而调用方传的是 UTC → 白天会被误判深夜）。故此处改用
    #   **UTC 时刻**表达"上海 10:00 / 上海 23:30"，语义与原断言一致。
    r = evaluate_habit_prompt(
        p, date(2026, 9, 23), datetime(2026, 9, 23, 2, 0, tzinfo=UTC), 0, 0, policy
    )
    assert r["send"] is True
    r2 = evaluate_habit_prompt(
        p, date(2026, 9, 23), datetime(2026, 9, 23, 15, 30, tzinfo=UTC), 0, 0, policy
    )
    assert r2["send"] is False
