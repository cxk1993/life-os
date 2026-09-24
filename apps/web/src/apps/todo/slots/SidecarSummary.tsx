import { useQuery } from "@tanstack/react-query";
import { todoApi } from "../api";

/**
 * E5 首例：窗口侧栏卡片（`window.sidecar` 扩展点，attachTo: "calendar"）。
 * 挂在日程表窗侧栏的「今日待办摘要」——精简版 DashboardCard。
 * 铁律同 DashboardCard：永远能渲染空状态（后端禁用/无数据都给 0 兜底）。
 */
export default function SidecarSummary() {
  const { data } = useQuery({
    queryKey: ["todo", "summary"],
    queryFn: () => todoApi.summary(),
    retry: 1,
  });

  const today = data?.today ?? 0;
  const overdue = data?.overdue ?? 0;

  return (
    <div className="sidecar-card" data-testid="todo-sidecar-summary">
      <div className="sidecar-card__title">今日待办</div>
      <div className="sidecar-card__body">
        <span className="sidecar-card__num">{today}</span>
        <span className="sidecar-card__lbl"> 项今日</span>
        {overdue > 0 ? <span className="sidecar-card__overdue"> · {overdue} 项逾期</span> : null}
      </div>
      {today === 0 && overdue === 0 ? (
        <div className="sidecar-card__empty">今天没有待办</div>
      ) : null}
    </div>
  );
}
