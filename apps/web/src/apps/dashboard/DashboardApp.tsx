/**
 * 成长罗盘主界面（T11 最小首屏）。
 * 一次拉 /api/v1/dashboard/overview；面板：Today / Money / Review / Growth / 系统健康；
 * 用 T14 SlotHost 渲染其它插件挂在 dashboard.card 上的卡片。
 */
import { useQuery } from "@tanstack/react-query";
import { SlotHost } from "@/kernel/slots/SlotHost";
import { dashboardApi } from "./api";
import GrowthPanel from "./GrowthPanel";
import MoneyPanel from "./MoneyPanel";
import ReviewPanel from "./ReviewPanel";
import SystemHealth from "./SystemHealth";
import TodayPanel from "./TodayPanel";
import "./dashboard.css";

const PHILOSOPHY = ["目标导向", "AI 直接可加速过程", "过程明确化"];

export default function DashboardApp() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["dashboard", "overview"],
    queryFn: () => dashboardApi.overview(),
    retry: 1,
  });

  if (isLoading) {
    return (
      <div className="dash-root">
        <div className="dash-loading">正在聚合各模块数据…</div>
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="dash-root">
        <div className="dash-error" role="alert">
          概览暂不可用：{error instanceof Error ? error.message : "未知错误"}
          <div>
            <button type="button" onClick={() => void refetch()}>
              重试
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="dash-root" data-testid="dashboard-root">
      <div className="dash-banner" aria-label="设计哲学">
        {PHILOSOPHY.map((w) => (
          <span key={w} className="dash-banner__tag">
            {w}
          </span>
        ))}
        <span className="dash-date">首屏日期 {data.date}</span>
      </div>

      <div className="dash-grid">
        <TodayPanel today={data.today} />
        <MoneyPanel money={data.money} />
        <ReviewPanel review={data.review} />
        <GrowthPanel growth={data.growth} />
      </div>

      <SystemHealth
        system={data.system}
        cards={data.cards}
        cardsHint={data.cards_hint}
      />

      <section className="dash-card" aria-label="插件卡片">
        <div className="dash-card__title">扩展卡片（dashboard.card）</div>
        <div className="dash-card__body">
          <SlotHost
            slot="dashboard.card"
            className="dash-slot-host"
            fallback={
              <div className="dash-muted" data-testid="slot-empty">
                暂无插件卡片挂载（calendar / todo / habits / agents 声明了该扩展点；
                需 PluginProvider 加载入口后出现）
              </div>
            }
          />
        </div>
      </section>
    </div>
  );
}
