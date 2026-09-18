/** 钱面板：资产快照（finance snapshots）或账本汇总（finance summary）。 */
import type { MoneyBlock } from "./api";
import { formatCents, isDegraded } from "./api";

export default function MoneyPanel({ money }: { money: MoneyBlock }) {
  const snap = money.snapshot ?? {};
  const summary = money.summary ?? {};
  const snapStatus = String(snap.status ?? "ok");
  const sumStatus = String(summary.status ?? "ok");
  const snapDown = isDegraded(snapStatus);
  const sumDown = isDegraded(sumStatus);
  const snapEmpty = snap.empty === true;

  const totalAsset = typeof snap.total_asset === "number" ? snap.total_asset : null;
  const net = typeof summary.net_cents === "number" ? summary.net_cents : null;

  return (
    <section className="dash-card" aria-label="钱">
      <div className="dash-card__title">钱</div>
      <div className="dash-card__body">
        <div className="dash-stats">
          <div className="dash-stat">
            <span className="dash-stat__num" data-testid="money-asset">
              {snapDown || totalAsset === null ? "—" : formatCents(totalAsset)}
            </span>
            <span className="dash-stat__lbl">总资产（分→元）</span>
          </div>
          <div className="dash-stat">
            <span className="dash-stat__num" data-testid="money-net">
              {sumDown || net === null ? "—" : formatCents(net)}
            </span>
            <span className="dash-stat__lbl">区间净收支</span>
          </div>
        </div>
        {snapDown ? (
          <div className="dash-degraded" role="status">
            理财模块暂不可用
          </div>
        ) : snapEmpty ? (
          <div className="dash-muted">暂无资产快照（可先同步 BeeCount）</div>
        ) : null}
        <div className="dash-muted" data-testid="money-source">
          来源：GET /api/v1/finance/snapshots · GET /api/v1/finance/summary
        </div>
      </div>
    </section>
  );
}
