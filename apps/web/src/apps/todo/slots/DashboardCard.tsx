import { useQuery } from "@tanstack/react-query";
import { todoApi } from "../api";

/**
 * 概览页卡片（dashboard.card 扩展点）。
 * 铁律：永远能渲染空状态——后端禁用/无数据都不能崩。
 * 用 summary 接口，数据缺失时给 0 兜底。
 */
export default function DashboardCard() {
  const { data } = useQuery({
    queryKey: ["todo", "summary"],
    queryFn: () => todoApi.summary(),
    retry: 1,
  });

  const today = data?.today ?? 0;
  const overdue = data?.overdue ?? 0;
  const weekDone = data?.week_done ?? 0;

  return (
    <div className="card">
      <div className="card__title">待办</div>
      <div className="card__body todo-dash">
        <div className="todo-dash__stats">
          <div className="todo-dash__stat">
            <span className="todo-dash__num">{today}</span>
            <span className="todo-dash__lbl">今日</span>
          </div>
          <div className="todo-dash__stat">
            <span className="todo-dash__num">{overdue}</span>
            <span className="todo-dash__lbl">逾期</span>
          </div>
          <div className="todo-dash__stat">
            <span className="todo-dash__num">{weekDone}</span>
            <span className="todo-dash__lbl">本周完成</span>
          </div>
        </div>
        {today === 0 && overdue === 0 ? (
          <div className="tiny" style={{ color: "var(--txt-faint)" }}>
            今天没有待办
          </div>
        ) : null}
      </div>
    </div>
  );
}
