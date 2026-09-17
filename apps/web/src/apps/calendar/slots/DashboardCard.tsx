/**
 * 仪表盘卡片插槽（manifest slots: ["dashboard.card"]）。
 * 在仪表盘里展示「今天的待办/日程」概览，点击可跳转到本周日程。
 * 复用 useCalendarEvents 拉取真实数据（仅读），不引入额外状态。
 */

import { useMemo } from "react";
import { useCalendarEvents } from "../hooks/useCalendarEvents";
import { addDays, startOfDay } from "../lib/time";

export function DashboardCard() {
  const today = startOfDay(new Date());
  const range = useMemo(
    () => ({ from: today.toISOString(), to: addDays(today, 1).toISOString() }),
    [],
  );
  const { events, isLoading } = useCalendarEvents(range);

  const todayEvents = events.filter((e) => {
    const s = startOfDay(new Date(e.start_at));
    return s.getTime() === today.getTime();
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
