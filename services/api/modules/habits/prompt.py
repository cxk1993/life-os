"""O3 · 习惯锚点提示（Fogg B=MAP 的 Prompt 半边）。

配置在 habit.prompt；发送一律过 N2 策略闸。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

from modules.calendar.notify_policy import NotifyPolicy, evaluate


@dataclass(frozen=True)
class HabitPrompt:
    anchor: str  # after_meal | after_wake | at_time
    at: str = "07:30"
    days: tuple[int, ...] = (0, 1, 2, 3, 4, 5, 6)  # Mon=0
    message: str = ""


ANCHOR_WINDOWS = {
    "after_wake": (time(6, 30), time(8, 30)),
    "after_meal": (time(12, 30), time(13, 30)),
    "at_time": (time(0, 0), time(23, 59)),
}


def parse_prompt(raw: dict[str, Any] | None) -> HabitPrompt | None:
    if not raw:
        return None
    anchor = str(raw.get("anchor") or "at_time")
    if anchor not in ANCHOR_WINDOWS:
        return None
    days = tuple(int(d) for d in (raw.get("days") or list(range(7))))
    return HabitPrompt(
        anchor=anchor,
        at=str(raw.get("at") or "07:30"),
        days=days,
        message=str(raw.get("message") or ""),
    )


def planned_fire(prompt: HabitPrompt, d: date) -> datetime | None:
    if d.weekday() not in prompt.days:
        return None
    try:
        hh, mm = (int(x) for x in prompt.at.split(":")[:2])
        t = time(hh, mm)
    except Exception:
        lo, hi = ANCHOR_WINDOWS[prompt.anchor]
        t = lo
    lo, hi = ANCHOR_WINDOWS[prompt.anchor]
    # at_time 用 at；锚点窗取窗起点
    if prompt.anchor == "at_time":
        return datetime.combine(d, t)
    return datetime.combine(d, lo)


def evaluate_habit_prompt(
    prompt: HabitPrompt,
    d: date,
    now: datetime,
    sent_last_hour: int,
    sent_today: int,
    policy: NotifyPolicy | None = None,
) -> dict[str, Any]:
    fire = planned_fire(prompt, d)
    if fire is None:
        return {"send": False, "suppress_reason": "not_scheduled", "fire_at": None, "message": ""}
    decision = evaluate(
        planned=fire, now=now, sent_last_hour=sent_last_hour, sent_today=sent_today, policy=policy
    )
    return {
        "send": decision.send,
        "suppress_reason": decision.suppress_reason,
        "fire_at": decision.fire_at.isoformat(),
        "message": prompt.message or "该打卡啦",
    }
