"""D1-二期 · 健康趋势预警纯函数（JITAI 判定半边）。

发送侧一律走提醒策略闸（静默/频控）；本模块只回答「该不该提示、哪一档」。
红线：不下诊断；level 仅文案档位。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TrendAlert:
    should_alert: bool
    reason_code: str | None
    level: str  # nudge | rest | see_doctor


def trend_alert(
    sev_series: list[int | None],
    *,
    streak_days: int = 3,
    gte: int = 4,
) -> TrendAlert:
    """sev_series 按【旧→新】。None=无记录，不参与连升（过滤后比较）。"""
    xs = [s for s in sev_series if s is not None]
    if not xs:
        return TrendAlert(False, None, "nudge")
    if max(xs) >= gte:
        return TrendAlert(True, f"severity_gte:{gte}", "see_doctor")
    up = 0
    for i in range(1, len(xs)):
        up = up + 1 if xs[i] > xs[i - 1] else 0
        if up >= streak_days - 1:
            return TrendAlert(True, f"severity_streak_up:{streak_days}", "rest")
    return TrendAlert(False, None, "nudge")
