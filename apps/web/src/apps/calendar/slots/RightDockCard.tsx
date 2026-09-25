import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { ApiError } from "@/shared/api/client";
import { useDesktopStore } from "../../../kernel/store";
import { calendarApi } from "../api";

function localDay(d = new Date()): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/** U3 右栏 · 日程小日历（desktop.dock-right）。 */
export default function RightDockCard() {
  const openWindow = useDesktopStore((s) => s.openWindow);
  const today = localDay();
  const monthStart = localDay(new Date(new Date().getFullYear(), new Date().getMonth(), 1));
  const monthEnd = localDay(new Date(new Date().getFullYear(), new Date().getMonth() + 1, 0));

  const { data, isError, isLoading } = useQuery({
    queryKey: ["calendar", "right-card", monthStart],
    queryFn: async () => {
      try {
        return await calendarApi.listRange(monthStart, monthEnd);
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) return null;
        throw e;
      }
    },
    retry: 1,
    refetchOnWindowFocus: false,
  });

  const events = data ?? [];
  const todayList = useMemo(
    () =>
      events.filter((e) => {
        const s = String((e as { start_at?: string }).start_at ?? "");
        return s.slice(0, 10) === today;
      }),
    [events, today],
  );
  const markDays = useMemo(() => {
    const set = new Set<string>();
    for (const e of events) {
      const s = String((e as { start_at?: string }).start_at ?? "").slice(0, 10);
      if (s) set.add(s);
    }
    return set;
  }, [events]);

  const now = new Date();
  const firstDow = (new Date(now.getFullYear(), now.getMonth(), 1).getDay() + 6) % 7;
  const daysInMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate();
  const cells: (number | null)[] = [
    ...Array.from({ length: firstDow }, () => null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ];

  return (
    <div className="dock-card" data-testid="calendar-right-card">
      <button type="button" className="dock-card__head" onClick={() => openWindow("calendar")}>
        <span>日程</span>
        <span className="dock-card__sub">小日历</span>
        {todayList.length > 0 ? <span className="dock-card__count">{todayList.length}</span> : null}
      </button>
      {isLoading ? (
        <div className="dock-card__empty">…</div>
      ) : isError ? (
        <div className="dock-card__empty">暂时不可用</div>
      ) : data === null ? (
        <div className="dock-card__empty">未安装 · 去安装</div>
      ) : (
        <div>
          <div className="dock-mini-cal" aria-label="本月日程点阵">
            {cells.map((d, i) => {
              if (d === null) return <span key={i} className="dock-mini-cal__cell is-empty" />;
              const ds = localDay(new Date(now.getFullYear(), now.getMonth(), d));
              const isToday = ds === today;
              const has = markDays.has(ds);
              const cls =
                "dock-mini-cal__cell" +
                (isToday ? " is-today" : "") +
                (has ? " has-mark" : "");
              return (
                <span key={i} className={cls}>
                  {d}
                </span>
              );
            })}
          </div>
          {todayList.length === 0 ? (
            <div className="dock-card__empty">今日无日程</div>
          ) : (
            <ul className="dock-card__list">
              {todayList.slice(0, 5).map((e, i) => {
                const start = String((e as { start_at?: string }).start_at ?? "");
                const hhmm = start.slice(11, 16);
                const title = String((e as { title?: string }).title ?? "");
                return (
                  <li key={i} className="dock-card__item">
                    <span className="dock-card__txt">
                      {hhmm ? `${hhmm} ` : ""}
                      {title}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
