import HealthTrend from "./HealthTrend";

/** D1 · 健康概览卡（dashboard.card 扩展点）——直接复用趋势组件。 */
export default function DashboardCard() {
  return (
    <div className="card">
      <div className="card__title">健康</div>
      <div className="card__body">
        <HealthTrend />
      </div>
    </div>
  );
}
