"""TX-REMIND-01 V1 · 提醒策略闸（N2）：静默时段 + 频控 + lead 择时。

发送侧（桥 toast / push）唯一入口调用 evaluate()；抑制必须带 reason，禁止静默丢。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta


@dataclass(frozen=True)
class QuietHours:
    start: time = time(23, 0)
    end: time = time(7, 30)


@dataclass(frozen=True)
class RateLimit:
    max_per_hour: int = 3
    max_per_day: int = 12


@dataclass(frozen=True)
class Timing:
    mode: str = "lead"  # fixed | lead | just_in_time
    lead_minutes: int = 10


@dataclass(frozen=True)
class NotifyPolicy:
    quiet: QuietHours = field(default_factory=QuietHours)
    rate: RateLimit = field(default_factory=RateLimit)
    timing: Timing = field(default_factory=Timing)


@dataclass(frozen=True)
class Decision:
    send: bool
    fire_at: datetime
    suppress_reason: str | None


def _in_quiet(now: datetime, q: QuietHours) -> bool:
    t = now.time()
    if q.start <= q.end:
        return q.start <= t < q.end
    return t >= q.start or t < q.end


def evaluate(
    *,
    planned: datetime,
    now: datetime,
    sent_last_hour: int,
    sent_today: int,
    policy: NotifyPolicy | None = None,
) -> Decision:
    p = policy or NotifyPolicy()
    lead = p.timing.lead_minutes if p.timing.mode == "lead" else 0
    fire = planned - timedelta(minutes=lead)
    if _in_quiet(now, p.quiet) or _in_quiet(fire, p.quiet):
        return Decision(False, fire, "quiet_hours")
    if sent_last_hour >= p.rate.max_per_hour or sent_today >= p.rate.max_per_day:
        return Decision(False, fire, "rate_limited")
    return Decision(True, fire, None)
