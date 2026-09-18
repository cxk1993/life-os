import { useQuery } from "@tanstack/react-query";
import { habitsApi } from "../api";

/** 概览页卡片：今日完成 / 待完成 / 最长连击。空数据也要稳。 */
export default function DashboardCard() {
  const { data } = useQuery({
    queryKey: ["habits", "summary"],
    queryFn: () => habitsApi.summary(),
    retry: 1,
  });

  const total = data?.total ?? 0;
  const done = data?.done ?? 0;
  const best = data?.best_streak ?? 0;

  return (
    <div className="card">
      <div className="card__title">习惯</div>
      <div className="card__body">
        <div className="habits-dash__stats">
          <div className="habits-dash__stat">
            <span className="habits-dash__num">{total ? `${done}/${total}` : "—"}</span>
            <span className="habits-dash__lbl">今日</span>
          </div>
          <div className="habits-dash__stat">
            <span className="habits-dash__num">{best}</span>
            <span className="habits-dash__lbl">最长连击</span>
          </div>
        </div>
        {total === 0 ? (
          <div className="tiny" style={{ color: "var(--txt-faint)" }}>
            还没有习惯
          </div>
        ) : null}
      </div>
    </div>
  );
}
