/**
 * DateNavigator —— 月历式日记入口（T17）。
 *
 * 月历高亮「已有日记」的日期（来自 GET /month）。点某天 → onSelect(date)。
 * 纯展示组件；数据由父层注入（薄壳不重复造轮子）。
 */
import { useMemo } from "react";

export interface DateNavigatorProps {
  year: number;
  month: number; // 1-12
  days: string[]; // 已有日记 YYYY-MM-DD
  selectedDate?: string | null;
  today?: string | null;
  onSelect?: (date: string) => void;
  onShift?: (delta: number) => void; // 翻月 -1/+1
}

const WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"];

function pad2(n: number) {
  return String(n).padStart(2, "0");
}

export function DateNavigator({
  year,
  month,
  days,
  selectedDate,
  today,
  onSelect,
  onShift,
}: DateNavigatorProps) {
  const daySet = useMemo(() => new Set(days), [days]);

  // 当月 1 号是星期几（周一=0）
  const first = new Date(year, month - 1, 1);
  const lead = (first.getDay() + 6) % 7;
  const daysInMonth = new Date(year, month, 0).getDate();

  const cells: (string | null)[] = [];
  for (let i = 0; i < lead; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(`${year}-${pad2(month)}-${pad2(d)}`);

  return (
    <div className="diary-cal">
      <div className="diary-cal-head">
        <button type="button" onClick={() => onShift?.(-1)} aria-label="上一月">
          ‹
        </button>
        <span className="diary-cal-title">
          {year} 年 {month} 月
        </span>
        <button type="button" onClick={() => onShift?.(1)} aria-label="下一月">
          ›
        </button>
      </div>
      <div className="diary-cal-weekdays">
        {WEEKDAYS.map((w) => (
          <span key={w}>{w}</span>
        ))}
      </div>
      <div className="diary-cal-grid">
        {cells.map((date, i) =>
          date === null ? (
            <span key={`e${i}`} className="diary-cal-empty" />
          ) : (
            <button
              key={date}
              type="button"
              className={[
                "diary-cal-day",
                daySet.has(date) ? "has-entry" : "",
                selectedDate === date ? "selected" : "",
                today === date ? "today" : "",
              ].join(" ")}
              onClick={() => onSelect?.(date)}
            >
              {Number(date.slice(-2))}
            </button>
          ),
        )}
      </div>
    </div>
  );
}

export default DateNavigator;
