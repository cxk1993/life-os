/**
 * 月视图：标准 6×7 月历，每天格内列出当日事件的彩色小条。
 * 点击小条选中并在 Inspector 中编辑；点击空白格可在那天 00:00 新建。
 * 月视图为「概览」，不承载拖动/缩放（那些在日/周网格里）。
 */

import { useMemo } from "react";
import type { CalendarEvent } from "../api";
import { addDays, startOfDay, dayIndexInWeek } from "../lib/time";

interface Props {
  events: CalendarEvent[];
  /** 当前显示月份的任一日期（决定渲染哪个月）。 */
  anchor: Date;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  onCreateAt: (startISO: string) => void;
}

const WEEKDAY = ["一", "二", "三", "四", "五", "六", "日"];

function monthGridStart(anchor: Date): Date {
  // 以「包含本月 1 号的那一周的周一」为起点（与周视图 weekStart 对齐）
  const first = new Date(anchor.getFullYear(), anchor.getMonth(), 1);
  const wd = (first.getDay() + 6) % 7; // 周一=0
  return addDays(startOfDay(first), -wd);
}

export function MonthGrid({ events, anchor, selectedId, onSelect, onCreateAt }: Props) {
  const start = useMemo(() => monthGridStart(anchor), [anchor]);
  const days = useMemo(() => Array.from({ length: 42 }, (_, i) => addDays(start, i)), [start]);

  const byDay = useMemo(() => {
    const map = new Map<number, CalendarEvent[]>();
    for (const ev of events) {
      const s = startOfDay(new Date(ev.start_at));
      const key = Math.round(s.getTime() / 86_400_000);
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(ev);
    }
    return map;
  }, [events]);

  const todayKey = Math.round(startOfDay(new Date()).getTime() / 86_400_000);

  return (
    <div className="cal-month">
      <div className="cal-month-weekdays">
        {WEEKDAY.map((w) => (
          <div key={w} className="cal-month-weekday">
            周{w}
          </div>
        ))}
      </div>
      <div className="cal-month-grid">
        {days.map((d, i) => {
          const key = Math.round(d.getTime() / 86_400_000);
          const inMonth = d.getMonth() === anchor.getMonth();
          const dayEvents = byDay.get(key) ?? [];
          return (
            <div
              key={i}
              className={
                "cal-month-cell" + (inMonth ? "" : " outside") + (key === todayKey ? " today" : "")
              }
              onClick={(e) => {
                if ((e.target as HTMLElement).closest(".cal-month-chip")) return;
                onSelect(null);
                onCreateAt(
                  new Date(d.getFullYear(), d.getMonth(), d.getDate(), 9, 0).toISOString(),
                );
              }}
            >
              <div className="cal-month-date">{d.getDate()}</div>
              <div className="cal-month-chips">
                {dayEvents.slice(0, 3).map((ev) => (
                  <div
                    key={ev.id}
                    className={"cal-month-chip" + (selectedId === ev.id ? " selected" : "")}
                    style={{ background: ev.color || "var(--accent)" }}
                    title={ev.title}
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelect(ev.id);
                    }}
                  >
                    {ev.title}
                  </div>
                ))}
                {dayEvents.length > 3 ? (
                  <div className="cal-month-more">+{dayEvents.length - 3}</div>
                ) : null}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export { dayIndexInWeek };
