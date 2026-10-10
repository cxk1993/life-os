"""V1 · 提醒策略闸（N2）：静默时段 + 频控 + lead 择时。

★ 2026-09-26：静默时段/频控/提前量均已 env 可配；`CALENDAR_QUIET_ENABLED=false` 可整体关闭静默。

发送侧（桥 toast / push）唯一入口调用 evaluate()；抑制必须带 reason，禁止静默丢。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from core.config import read_setting


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


# ★ 2026-09-26 新增（astrbot · 主人「全修」）：
#   原先静默时段/频控/提前量**写死在代码里**（23:00–07:30 等），无法按需调整 ——
#   主人夜间事件收不到提醒正是被 quiet_hours 拦的（日志 reason=n2_suppress:quiet_hours）。
#   现改为「**env 可配，代码默认值不变**」：用 read_setting（os.environ 优先 → .env 回退），
#   解析失败一律**回落到原默认**（绝不因配置写错而失控）。
def _parse_time(raw: str | None, default: time) -> time:
    try:
        hh, mm = (raw or "").strip().split(":")
        return time(int(hh), int(mm))
    except Exception:  # noqa: BLE001 — 配置写错 → 回落默认，不抛
        return default


def _parse_int(raw: str | None, default: int, *, minimum: int = 0) -> int:
    try:
        return max(minimum, int((raw or "").strip()))
    except Exception:  # noqa: BLE001
        return default


# ★ 2026-09-26 新增（主人「深夜静默可以关掉」）：
#   `CALENDAR_QUIET_ENABLED=false` → 静默时段整体失效（24 小时都可推）。
#   默认 true（保持既有行为）。实现方式：让 start == end，则 `start <= t < end` 恒假。
def _quiet_enabled() -> bool:
    raw = (read_setting("CALENDAR_QUIET_ENABLED", "true") or "true").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _quiet_from_env() -> QuietHours:
    """静默时段（env：CALENDAR_QUIET_START / CALENDAR_QUIET_END，HH:MM）。

    `CALENDAR_QUIET_ENABLED=false` 时返回空区间（永不静默）。
    """
    if not _quiet_enabled():
        return QuietHours(start=time(0, 0), end=time(0, 0))  # 空区间 → 恒不静默
    return QuietHours(
        start=_parse_time(read_setting("CALENDAR_QUIET_START", "23:00"), time(23, 0)),
        end=_parse_time(read_setting("CALENDAR_QUIET_END", "07:30"), time(7, 30)),
    )


def _rate_from_env() -> RateLimit:
    """频控（env：CALENDAR_RATE_PER_HOUR / CALENDAR_RATE_PER_DAY）。"""
    return RateLimit(
        max_per_hour=_parse_int(read_setting("CALENDAR_RATE_PER_HOUR", "3"), 3, minimum=1),
        max_per_day=_parse_int(read_setting("CALENDAR_RATE_PER_DAY", "12"), 12, minimum=1),
    )


def _timing_from_env() -> Timing:
    """择时（env：CALENDAR_REMINDER_LEAD_MINUTES；mode 固定 lead）。"""
    return Timing(
        mode="lead",
        lead_minutes=_parse_int(
            read_setting("CALENDAR_REMINDER_LEAD_MINUTES", "10"), 10, minimum=0
        ),
    )


@dataclass(frozen=True)
class NotifyPolicy:
    quiet: QuietHours = field(default_factory=_quiet_from_env)
    rate: RateLimit = field(default_factory=_rate_from_env)
    timing: Timing = field(default_factory=_timing_from_env)


@dataclass(frozen=True)
class Decision:
    send: bool
    fire_at: datetime
    suppress_reason: str | None


# ★ 2026-09-26 修（astrbot · 主人「全修」）：**时区误判**（本文件最隐蔽的一枚）
#   原实现直接取 `now.time()` 与 QuietHours 比较 —— 但调用方传入的 now/fire 是
#   **UTC**（datetime.now(UTC)），而静默时段 23:00–07:30 是**本地（Asia/Shanghai）**
#   语义。于是 13:27 CST（= 05:27 UTC）被判成"深夜静默" → **白天提醒全被抑制**
#（生产 31 条 calendar_reminder_log 里 ok=0 的绝大多数是这条）。
#   修法：统一换算到本地时区再比时段；naive 值按 UTC 解释（与调用方一致）。
QUIET_TZ = ZoneInfo("Asia/Shanghai")


def _to_local(dt: datetime) -> datetime:
    """把（可能 tz-aware/naive 的）时间统一换算到本地时区。"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(QUIET_TZ)


def _in_quiet(now: datetime, q: QuietHours) -> bool:
    t = _to_local(now).time()
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
