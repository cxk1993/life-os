/** 成长罗盘占位：最小闭环返回空轴 + 说明，完整三轴后补。 */
import type { GrowthBlock } from "./api";

export default function GrowthPanel({ growth }: { growth: GrowthBlock }) {
  return (
    <section className="dash-card" aria-label="成长罗盘">
      <div className="dash-card__title">成长罗盘</div>
      <div className="dash-card__body">
        <div className="dash-stats">
          <div className="dash-stat">
            <span className="dash-stat__num" data-testid="growth-axes">
              {growth.axes?.length ?? 0}
            </span>
            <span className="dash-stat__lbl">成长轴</span>
          </div>
        </div>
        <div className="dash-muted" data-testid="growth-placeholder">
          {growth.placeholder || "完整成长罗盘后补"}
        </div>
        <div className="dash-muted">来源：GET /api/v1/dashboard/growth（占位）</div>
      </div>
    </section>
  );
}
