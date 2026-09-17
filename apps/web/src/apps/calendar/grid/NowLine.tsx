/**
 * 当前时间红线：随分钟移动，只在本周范围内当天那一列显示。
 * 每分钟 tick 一次（不需要 rAF / 秒级精度）。
 */

import { useEffect, useState } from "react";
import { addDays, startOfDay, MIN_MS, dayIndexInWeek } from "../lib/time";

interface Props {
  weekStart: Date;
  hourHeight: number;
  dayWidth: number;
  days: number;
}

function formatHM(d: Date): string {
  const h = String(d.getHours()).padStart(2, "0");
  const m = String(d.getMinutes()).padStart(2, "0");
  return `${h}:${m}`;
}

export function NowLine({ weekStart, hourHeight, dayWidth, days }: Props) {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(t);
  }, []);

  const dayIdx = dayIndexInWeek(now, weekStart);
  if (dayIdx < 0 || dayIdx >= days) return null;

  const colStart = addDays(startOfDay(weekStart), dayIdx);
  const mins = (now.getTime() - colStart.getTime()) / MIN_MS;
  const top = (mins / 60) * hourHeight;

  return (
    <div
      className="cal-nowline"
      style={{ left: dayIdx * dayWidth, width: dayWidth, top }}
      aria-hidden
    >
      <span className="cal-nowline-dot" />
      <span className="cal-nowline-label">{formatHM(now)}</span>
    </div>
  );
}
