import type { HealthRecord } from "../api";

/** D1 · 健康趋势聚合（纯函数，独立文件以保 react-refresh 只 export 组件）。 */

export interface TrendPoint {
  weekLabel: string; // "9/1"
  count: number;
  avgSeverity: number | null;
}

export const TREND_WEEKS = 8;

export function isoWeekStart(d: Date): Date {
  const day = (d.getDay() + 6) % 7; // 周一=0
  const start = new Date(d);
  start.setHours(0, 0, 0, 0);
  start.setDate(d.getDate() - day);
  return start;
}

/** 近 N 周按周聚合：症状频率 + 严重度均值（空周补 0）。 */
export function aggregateTrend(records: HealthRecord[], weeks: number = TREND_WEEKS): TrendPoint[] {
  const now = new Date();
  const thisWeekStart = isoWeekStart(now);
  // ★ 每桶存 weekStart 时间戳（findIndex 按时间戳匹配，避免数组下标=周偏移的错位）
  const buckets: (TrendPoint & { start: number })[] = [];
  for (let i = weeks - 1; i >= 0; i--) {
    const start = new Date(thisWeekStart);
    start.setDate(thisWeekStart.getDate() - i * 7);
    const label = `${start.getMonth() + 1}/${start.getDate()}`;
    buckets.push({ weekLabel: label, count: 0, avgSeverity: null, start: start.getTime() });
  }

  const sevSum: number[] = buckets.map(() => 0);
  const sevN: number[] = buckets.map(() => 0);

  for (const r of records) {
    const t = new Date(r.occurred_at);
    if (Number.isNaN(t.getTime())) continue;
    const ws = isoWeekStart(t).getTime();
    const idx = buckets.findIndex((b) => b.start === ws);
    if (idx < 0) continue;
    buckets[idx].count += 1;
    if (typeof r.severity === "number" && r.severity >= 1 && r.severity <= 5) {
      sevSum[idx] += r.severity;
      sevN[idx] += 1;
    }
  }
  for (let i = 0; i < buckets.length; i++) {
    if (sevN[i] > 0) buckets[i].avgSeverity = Math.round((sevSum[i] / sevN[i]) * 10) / 10;
  }
  return buckets.map((b) => ({
    weekLabel: b.weekLabel,
    count: b.count,
    avgSeverity: b.avgSeverity,
  }));
}

// ── D1 迭代 2（QS 前景/背景 · 惊讶时刻，MiMo 提议）──

export interface TrendInsight {
  kind: "up" | "down";
  /** 症状名（title）。 */
  title: string;
  /** 最近一周记录次数。 */
  recentCount: number;
  /** 之前 4 周均值。 */
  priorAvg: number;
  message: string;
}

/**
 * 症状级洞察（"惊讶时刻"）：近一周某症状记录显著高于/低于之前几周时给一句提示。
 * - up：recentCount ≥ 2 且 ≥ priorAvg×2（且 priorAvg ≥ 0.5，防除零噪声）
 * - down：priorAvg ≥ 2 且 recentCount ≤ priorAvg×0.5
 * - 多症状显著时取偏差最大者；无显著变化返回 null（不打扰）
 * 纯函数、零副作用；阈值是启发式，可后续调参。
 */
export function deriveInsight(
  records: HealthRecord[],
  weeks: number = TREND_WEEKS,
): TrendInsight | null {
  const now = new Date();
  const thisWeekStart = isoWeekStart(now);
  const weekStarts: number[] = [];
  for (let i = weeks - 1; i >= 0; i--) {
    const start = new Date(thisWeekStart);
    start.setDate(thisWeekStart.getDate() - i * 7);
    weekStarts.push(start.getTime());
  }

  // 按症状名分组 → 每周计数（桶下标 = weekStarts 下标）
  const perTitle = new Map<string, number[]>();
  for (const r of records) {
    if (r.kind !== "symptom" || !r.title) continue;
    const t = new Date(r.occurred_at);
    if (Number.isNaN(t.getTime())) continue;
    const ws = isoWeekStart(t).getTime();
    const idx = weekStarts.indexOf(ws);
    if (idx < 0) continue;
    if (!perTitle.has(r.title)) perTitle.set(r.title, new Array(weeks).fill(0));
    perTitle.get(r.title)![idx] += 1;
  }

  let best: TrendInsight | null = null;
  let bestDelta = 0;
  for (const [title, counts] of perTitle) {
    const recent = counts[counts.length - 1];
    const prior = counts.slice(0, -1).slice(-4);
    const priorSum = prior.reduce((s, n) => s + n, 0);
    const priorAvg = priorSum / Math.max(1, prior.length);
    if (recent >= 2 && priorAvg >= 0.5 && recent >= priorAvg * 2) {
      const delta = recent - priorAvg;
      if (delta > bestDelta) {
        bestDelta = delta;
        best = {
          kind: "up",
          title,
          recentCount: recent,
          priorAvg: Math.round(priorAvg * 10) / 10,
          message: `近一周【${title}】记录 ${recent} 次，明显高于之前几周（均值 ${Math.round(priorAvg * 10) / 10}）——要不要记一条备注？`,
        };
      }
    } else if (priorAvg >= 2 && recent <= priorAvg * 0.5) {
      const delta = priorAvg - recent;
      if (delta > bestDelta) {
        bestDelta = delta;
        best = {
          kind: "down",
          title,
          recentCount: recent,
          priorAvg: Math.round(priorAvg * 10) / 10,
          message: `近一周【${title}】记录 ${recent} 次，比之前几周（均值 ${Math.round(priorAvg * 10) / 10}）明显减少——继续保持！`,
        };
      }
    }
  }
  return best;
}
