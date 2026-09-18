/** 今日面板：日程数 / 待办 / 习惯 x/n。数字全部来自 /api/v1/dashboard/overview。 */
import type { TodayBlock } from "./api";
import { isDegraded } from "./api";

function Stat({
  label,
  value,
  degraded,
}: {
  label: string;
  value: string;
  degraded?: boolean;
}) {
  return (
    <div className="dash-stat">
      <span className="dash-stat__num" data-testid={`today-${label}`}>
        {degraded ? "—" : value}
      </span>
      <span className="dash-stat__lbl">{label}</span>
    </div>
  );
}

export default function TodayPanel({ today }: { today: TodayBlock }) {
  const { counts } = today;
  const calDown = isDegraded(today.calendar?.status);
  const todoDown = isDegraded(today.todo?.status);
  const habitsDown = isDegraded(today.habits?.status);

  const habitsValue =
    counts.habits_done !== null && counts.habits_total !== null
      ? `${counts.habits_done}/${counts.habits_total}`
      : "—";

  return (
    <section className="dash-card" aria-label="今日">
      <div className="dash-card__title">今天 · {today.date}</div>
      <div className="dash-card__body">
        <div className="dash-stats">
          <Stat
            label="日程"
            value={counts.calendar_events !== null ? String(counts.calendar_events) : "—"}
            degraded={calDown}
          />
          <Stat
            label="待办"
            value={counts.todo_open !== null ? String(counts.todo_open) : "—"}
            degraded={todoDown}
          />
          <Stat label="习惯" value={habitsValue} degraded={habitsDown} />
        </div>
        {(calDown || todoDown || habitsDown) && (
          <div className="dash-degraded" role="status">
            该模块暂不可用（超时或故障），其余数字仍来自真实 API
          </div>
        )}
      </div>
    </section>
  );
}
