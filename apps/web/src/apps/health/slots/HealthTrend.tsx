import { useQuery } from "@tanstack/react-query";
import { healthApi } from "../api";
import { aggregateTrend, deriveInsight, TREND_WEEKS, type TrendPoint } from "./trend";

/** D1 · 健康趋势图（TX-HEALTH-01）。
 * dashboard.card 与 window.sidecar(health) 双形态共用本组件。
 * 铁律：永远能渲染空态（无记录时给引导，不崩）。
 * 迭代 2（QS 前景/背景）：图表=前景，deriveInsight 的「惊讶时刻」=背景提示。
 */

/** 纯 SVG 迷你趋势（柱 = 频率，折线 = 严重度均值；无外部图表库）。 */
function TrendChart({ points }: { points: TrendPoint[] }) {
  const W = 260;
  const H = 90;
  const padL = 4;
  const padR = 4;
  const padT = 8;
  const padB = 16;
  const innerW = W - padL - padR;
  const innerH = H - padT - padB;
  const maxCount = Math.max(1, ...points.map((p) => p.count));
  const barW = Math.max(4, Math.floor(innerW / points.length) - 6);

  return (
    <svg
      className="health-trend__chart"
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label="近 8 周症状趋势"
      data-testid="health-trend-chart"
    >
      {points.map((p, i) => {
        const x = padL + (innerW / points.length) * i + (innerW / points.length - barW) / 2;
        const barH = (p.count / maxCount) * innerH;
        const y = padT + innerH - barH;
        return (
          <rect
            key={p.weekLabel}
            x={x}
            y={y}
            width={barW}
            height={Math.max(1, barH)}
            className="health-trend__bar"
            data-count={p.count}
          >
            <title>{`${p.weekLabel}：${p.count} 次${p.avgSeverity != null ? `，均值 ${p.avgSeverity}` : ""}`}</title>
          </rect>
        );
      })}
      {points.length > 1 &&
        points.map((p, i) => {
          if (p.avgSeverity == null || i === 0) return null;
          const prev = points[i - 1];
          if (prev.avgSeverity == null) return null;
          const x1 = padL + (innerW / points.length) * (i - 1) + innerW / points.length / 2;
          const y1 = padT + innerH - ((prev.avgSeverity - 1) / 4) * innerH;
          const x2 = padL + (innerW / points.length) * i + innerW / points.length / 2;
          const y2 = padT + innerH - ((p.avgSeverity - 1) / 4) * innerH;
          return (
            <line
              key={`sev-${p.weekLabel}`}
              x1={x1}
              y1={y1}
              x2={x2}
              y2={y2}
              className="health-trend__sev-line"
            />
          );
        })}
      {points.map((p, i) => {
        if (p.avgSeverity == null) return null;
        const x = padL + (innerW / points.length) * i + innerW / points.length / 2;
        const y = padT + innerH - ((p.avgSeverity - 1) / 4) * innerH;
        return (
          <circle
            key={`sev-dot-${p.weekLabel}`}
            cx={x}
            cy={y}
            r={2.5}
            className="health-trend__sev-dot"
          />
        );
      })}
      {points.map((p, i) => (
        <text
          key={`lbl-${p.weekLabel}`}
          x={padL + (innerW / points.length) * i + innerW / points.length / 2}
          y={H - 4}
          textAnchor="middle"
          className="health-trend__lbl"
        >
          {p.weekLabel}
        </text>
      ))}
    </svg>
  );
}

export default function HealthTrend() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["health", "trend"],
    queryFn: async () => {
      const from = new Date();
      from.setDate(from.getDate() - (TREND_WEEKS - 1) * 7);
      const to = new Date();
      const recs = await healthApi.list({
        kind: "symptom",
        from: from.toISOString().slice(0, 10),
        to: to.toISOString().slice(0, 10),
      });
      return {
        points: aggregateTrend(recs, TREND_WEEKS),
        // 迭代 2：惊讶时刻（QS 背景层）——显著变化才提示，无变化 null（不打扰）
        insight: deriveInsight(recs, TREND_WEEKS),
      };
    },
    retry: 1,
  });

  if (isLoading) {
    return <div className="health-trend">加载趋势…</div>;
  }
  if (isError) {
    return <div className="health-trend">趋势暂时不可用</div>;
  }
  const points = data?.points ?? [];
  const insight = data?.insight ?? null;
  const total = points.reduce((s, p) => s + p.count, 0);
  return (
    <div className="health-trend" data-testid="health-trend">
      <div className="health-trend__head">
        <span className="health-trend__title">症状趋势（近 8 周）</span>
        <span className="health-trend__total">{total} 次</span>
      </div>
      {total === 0 ? (
        <div className="health-trend__empty">记几条症状记录，就能看到趋势</div>
      ) : (
        <TrendChart points={points} />
      )}
      {insight && (
        <div
          className={`health-trend__insight health-trend__insight--${insight.kind}`}
          data-testid="health-trend-insight"
          role="note"
        >
          {insight.message}
        </div>
      )}
      <div className="health-trend__legend">
        <span className="health-trend__legend-bar">▮ 频率</span>
        <span className="health-trend__legend-line">― 严重度均值</span>
      </div>
    </div>
  );
}
