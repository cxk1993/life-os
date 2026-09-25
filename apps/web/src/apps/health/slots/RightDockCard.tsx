import { useQuery } from "@tanstack/react-query";
import { ApiError } from "@/shared/api/client";
import { useDesktopStore } from "../../../kernel/store";
import { healthApi, type HealthRecord } from "../api";

/** U3 右栏 · 健康（记录 + 待办/复诊）。 */
export default function RightDockCard() {
  const openWindow = useDesktopStore((s) => s.openWindow);
  const { data, isError, isLoading } = useQuery({
    queryKey: ["health", "right-card"],
    queryFn: async (): Promise<HealthRecord[] | null> => {
      try {
        return await healthApi.list();
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) return null;
        throw e;
      }
    },
    retry: 1,
    refetchOnWindowFocus: false,
  });

  const rows = data ?? [];
  const followups = rows.filter((r) => r.followup_needed);
  const recent = rows.slice(0, 3);

  return (
    <div className="dock-card" data-testid="health-right-card">
      <button type="button" className="dock-card__head" onClick={() => openWindow("health")}>
        <span>健康</span>
        <span className="dock-card__sub">记录与待办</span>
        {followups.length > 0 ? <span className="dock-card__count">{followups.length}</span> : null}
      </button>
      {isLoading ? (
        <div className="dock-card__empty">…</div>
      ) : isError ? (
        <div className="dock-card__empty">暂时不可用</div>
      ) : data === null ? (
        <div className="dock-card__empty">未安装 · 去安装</div>
      ) : rows.length === 0 ? (
        <div className="dock-card__empty">还没有健康记录</div>
      ) : (
        <div>
          {followups.length > 0 ? (
            <ul className="dock-card__list">
              {followups.slice(0, 3).map((r) => (
                <li key={r.id} className="dock-card__item is-alert">
                  <span className="dock-card__txt">
                    待跟进 · {r.title}
                    {r.followup_due ? `（${String(r.followup_due).slice(0, 10)}）` : ""}
                  </span>
                </li>
              ))}
            </ul>
          ) : null}
          <ul className="dock-card__list">
            {recent.map((r) => (
              <li key={r.id} className="dock-card__item">
                <span className="dock-card__txt">
                  {r.kind ? `[${r.kind}] ` : ""}
                  {r.title}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
