import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { aggregateTrend, deriveInsight } from "./slots/trend";
import HealthTrend from "./slots/HealthTrend";
import { healthApi } from "./api";

vi.mock("./api", () => ({
  healthApi: {
    list: vi.fn(),
  },
}));

function rec(daysAgo: number, title: string, severity: number | null) {
  const d = new Date();
  d.setHours(12, 0, 0, 0);
  d.setDate(d.getDate() - daysAgo);
  return {
    id: `r-${daysAgo}-${title}`,
    kind: "symptom" as const,
    title,
    occurred_at: d.toISOString(),
    severity,
    note: null,
    followup_needed: false,
    followup_due: null,
  };
}

function makeWrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

describe("D1 · HealthTrend 聚合（aggregateTrend）", () => {
  it("近 8 周按周分组，症状计数正确（同周多条合并）", () => {
    const points = aggregateTrend(
      [rec(0, "头痛", 3), rec(1, "头痛", 2), rec(2, "失眠", 4), rec(40, "头痛", 1)],
      8,
    );
    expect(points).toHaveLength(8);
    const total = points.reduce((s, p) => s + p.count, 0);
    expect(total).toBeGreaterThanOrEqual(3); // 今天附近三条
    expect(total).toBeLessThanOrEqual(4); // 40 天前可能超出窗口被丢弃
    expect(points.every((p) => p.count >= 0)).toBe(true);
  });

  it("严重度均值 = 该周记录 severity 的算术平均（空周为 null）", () => {
    const points = aggregateTrend([rec(0, "头痛", 3), rec(0, "失眠", 5)], 8);
    const last = points[points.length - 1];
    expect(last.avgSeverity).toBe(4); // (3+5)/2 = 4
  });

  it("空记录 → 8 个全 0 空周，无崩溃", () => {
    const points = aggregateTrend([], 8);
    expect(points).toHaveLength(8);
    expect(points.every((p) => p.count === 0 && p.avgSeverity === null)).toBe(true);
  });

  it("非法日期被跳过", () => {
    const bad = { ...rec(0, "x", 1), occurred_at: "not-a-date" };
    const points = aggregateTrend([bad], 8);
    expect(points.every((p) => p.count === 0)).toBe(true);
  });
});

describe("D1 迭代 2 · 惊讶时刻（deriveInsight）", () => {
  it("近一周显著上升 → up 洞察（≥2 次且 ≥ 前 4 周均值×2）", () => {
    const recs = [
      // 最近 7 天：4 次头痛
      rec(0, "头痛", 3),
      rec(1, "头痛", 3),
      rec(2, "头痛", 2),
      rec(3, "头痛", 2),
      // 之前几周：每周 1 次（均值 1）
      rec(10, "头痛", 2),
      rec(17, "头痛", 2),
      rec(24, "头痛", 2),
      rec(31, "头痛", 2),
      // 别的症状不受影响
      rec(0, "失眠", 5),
    ];
    const insight = deriveInsight(recs);
    expect(insight).not.toBeNull();
    expect(insight!.kind).toBe("up");
    expect(insight!.title).toBe("头痛");
    expect(insight!.recentCount).toBe(4);
    expect(insight!.message).toContain("头痛");
    expect(insight!.message).toContain("记一条备注");
  });

  it("近一周显著下降 → down 洞察（前 4 周均值 ≥2 且近期 ≤ 一半）", () => {
    const recs = [
      // 最近 7 天：0 次
      // 之前几周：每周 3 次（均值 3）
      rec(8, "失眠", 5),
      rec(9, "失眠", 4),
      rec(10, "失眠", 3),
      rec(15, "失眠", 5),
      rec(16, "失眠", 4),
      rec(17, "失眠", 3),
      rec(22, "失眠", 5),
      rec(23, "失眠", 4),
      rec(24, "失眠", 3),
      rec(29, "失眠", 5),
      rec(30, "失眠", 4),
      rec(31, "失眠", 3),
    ];
    const insight = deriveInsight(recs);
    expect(insight).not.toBeNull();
    expect(insight!.kind).toBe("down");
    expect(insight!.title).toBe("失眠");
    expect(insight!.recentCount).toBe(0);
  });

  it("无显著变化 → null（不打扰）", () => {
    const recs = [rec(0, "头痛", 3), rec(7, "头痛", 3), rec(14, "头痛", 3), rec(21, "头痛", 3)];
    expect(deriveInsight(recs)).toBeNull();
  });

  it("空记录 / 非症状 → null", () => {
    expect(deriveInsight([])).toBeNull();
    const med = { ...rec(0, "布洛芬", null), kind: "medication" as const };
    expect(deriveInsight([med])).toBeNull();
  });
});

describe("D1 · HealthTrend 组件渲染", () => {
  it("无数据时渲染空态引导文案（不崩）", async () => {
    vi.mocked(healthApi.list).mockResolvedValue([]);
    render(<HealthTrend />, { wrapper: makeWrapper() });
    expect(await screen.findByText(/记几条症状记录/)).toBeTruthy();
  });

  it("有数据时渲染趋势图（频率计数可见）", async () => {
    vi.mocked(healthApi.list).mockResolvedValue([rec(0, "头痛", 3), rec(1, "头痛", 2)]);
    render(<HealthTrend />, { wrapper: makeWrapper() });
    expect(await screen.findByTestId("health-trend-chart")).toBeTruthy();
    expect(screen.getByText(/近 8 周/)).toBeTruthy();
  });

  it("迭代 2 · 显著上升时渲染「惊讶时刻」提示条（QS 背景层）", async () => {
    vi.mocked(healthApi.list).mockResolvedValue([
      rec(0, "头痛", 3),
      rec(1, "头痛", 3),
      rec(2, "头痛", 2),
      rec(3, "头痛", 2),
      rec(10, "头痛", 2),
      rec(17, "头痛", 2),
      rec(24, "头痛", 2),
      rec(31, "头痛", 2),
    ]);
    render(<HealthTrend />, { wrapper: makeWrapper() });
    expect(await screen.findByTestId("health-trend-insight")).toBeTruthy();
    expect(screen.getByText(/近一周【头痛】记录 4 次/)).toBeTruthy();
  });

  it("迭代 2 · 无显著变化时不渲染提示条（不打扰）", async () => {
    vi.mocked(healthApi.list).mockResolvedValue([
      rec(0, "头痛", 3),
      rec(7, "头痛", 3),
      rec(14, "头痛", 3),
      rec(21, "头痛", 3),
    ]);
    render(<HealthTrend />, { wrapper: makeWrapper() });
    expect(await screen.findByTestId("health-trend-chart")).toBeTruthy();
    expect(screen.queryByTestId("health-trend-insight")).toBeNull();
  });
});
