/**
 * 仪表盘卡片插槽（manifest slots: ["dashboard.card"]）。
 * 在仪表盘里展示「今天的待办/日程」概览，点击可跳转到本周日程。
 * 复用 useCalendarEvents 拉取真实数据（仅读），不引入额外状态。
 */

import { useMemo } from "react";
import { useCalendarEvents } from "../hooks/useCalendarEvents";
import { DAY_MS, formatSH, shWallClock, shWallParts, startOfDay } from "../lib/time";

export function DashboardCard() {
  // 今日窗口以东八区墙钟 00:00 为起点，from/to 带 +08:00（与 CalendarApp 一致）。
  const now = new Date();
  const p = shWallParts(now);
  const todaySh = shWallClock(p.y, p.mo, p.d, 0, 0, 0, 0);
  const range = useMemo(
    () => ({ from: formatSH(todaySh), to: formatSH(new Date(todaySh.getTime() + DAY_MS)) }),
    [],
  );
  const { events, isLoading } = useCalendarEvents(range);

  const todayEvents = events.filter((e) => {
    const s = startOfDay(new Date(e.start_at));
    return s.getTime() === todaySh.getTime();
  });

  return (
    <div className="cal-dash-card">
      <div className="cal-dash-head">今日日程</div>
      {isLoading ? (
        <div className="cal-dash-empty">加载中…</div>
      ) : todayEvents.length === 0 ? (
        <div className="cal-dash-empty">今天没有安排</div>
      ) : (
        <ul className="cal-dash-list">
          {todayEvents.slice(0, 5).map((e) => (
            <li key={e.id} className="cal-dash-item">
              <span className="cal-dash-dot" style={{ background: e.color || "var(--accent)" }} />
              <span className="cal-dash-time">{e.start_at.slice(11, 16)}</span>
              <span className="cal-dash-title">{e.title}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
