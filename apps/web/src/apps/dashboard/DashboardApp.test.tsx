/**
 * 成长罗盘前端测试。网络层全部 mock，不打真实后端。
 * SlotHost 场景：注册 calendar/todo/habits/agents 贡献后应能出现。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { useDesktopStore } from "@/kernel/store";
import {
  clearContributions,
  registerContributions,
  unregisterContributions,
} from "@/kernel/slots/contributions";
import DashboardApp from "./DashboardApp";
import { formatCents } from "./api";
import type { Overview } from "./api";

const overview: Overview = {
  date: "2026-09-18",
  today: {
    date: "2026-09-18",
    calendar: { status: "ok", value: [{ id: "e1" }, { id: "e2" }] },
    todo: { status: "ok", today: 3, overdue: 1, week_done: 5 },
    habits: { status: "ok", total: 4, done: 2, pending: 2, rest: 0, best_streak: 7 },
    counts: {
      calendar_events: 2,
      todo_open: 3,
      habits_done: 2,
      habits_total: 4,
    },
  },
  money: {
    snapshot: { status: "ok", total_asset: 123456, cash: 23456, invest: 100000 },
    summary: { status: "ok", expense_cents: 1000, income_cents: 2000, net_cents: 1000 },
  },
  review: {
    source: { status: "ok", mode: "mock", path: "mock", upstream_online: true, message: "ok" },
  },
  growth: { axes: [], placeholder: "完整成长罗盘后补" },
  system: [
    { id: "calendar", name: "日程表", status: "ok" },
    { id: "todo", name: "待办", status: "ok" },
    { id: "habits", name: "习惯", status: "ok" },
    { id: "finance", name: "理财", status: "ok" },
    { id: "review", name: "复盘", status: "ok" },
    { id: "agents", name: "AI 编排", status: "ok" },
  ],
  cards: [
    { pluginId: "calendar", name: "日程表", slot: "dashboard.card" },
    { pluginId: "todo", name: "todo", slot: "dashboard.card" },
    { pluginId: "habits", name: "习惯打卡", slot: "dashboard.card" },
    { pluginId: "agents", name: "AI 编排", slot: "dashboard.card" },
  ],
  cards_hint: "其它插件挂在 dashboard.card 上的卡片由前端 SlotHost 渲染",
  meta: { timeout_ms: 800, elapsed_ms: 42 },
};

const degraded: Overview = {
  ...overview,
  today: {
    ...overview.today,
    todo: { status: "error", detail: "todo down" },
    counts: {
      calendar_events: 2,
      todo_open: null,
      habits_done: 2,
      habits_total: 4,
    },
  },
  money: {
    snapshot: { status: "timeout", detail: "超过 800ms" },
    summary: { status: "ok", net_cents: 0 },
  },
  system: overview.system.map((s) =>
    s.id === "todo" ? { ...s, status: "error" as const, detail: "down" } : s,
  ),
};

vi.mock("@/shared/api/events", () => ({
  usePluginEvent: () => {},
}));

vi.mock("./api", async () => {
  const actual = await vi.importActual<typeof import("./api")>("./api");
  return {
    ...actual,
    dashboardApi: {
      overview: vi.fn().mockResolvedValue({
        date: "2026-09-18",
        today: {
          date: "2026-09-18",
          calendar: { status: "ok" },
          todo: { status: "ok" },
          habits: { status: "ok" },
          counts: {
            calendar_events: 0,
            todo_open: 0,
            habits_done: 0,
            habits_total: 0,
          },
        },
        money: { snapshot: { status: "ok" }, summary: { status: "ok" } },
        review: { source: { status: "ok" } },
        growth: { axes: [], placeholder: "" },
        system: [],
        cards: [],
        cards_hint: "",
        meta: {},
      }),
      today: vi.fn(),
      healthOfSystem: vi.fn(),
      growth: vi.fn(),
      manifest: vi.fn(),
    },
  };
});

function makeWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

function resetSlotState() {
  localStorage.clear();
  useDesktopStore.setState({ modules: {}, windows: [], topZ: 10, seq: 0 });
  clearContributions();
  unregisterContributions("calendar");
  unregisterContributions("todo");
  unregisterContributions("habits");
  unregisterContributions("agents");
}

function registerCardPlugin(id: string, name: string, text: string) {
  useDesktopStore.getState().registerModule({
    id,
    name,
    version: "0.1.0",
    kind: "builtin",
    entry: "",
    window: { w: 400, h: 300 },
    slots: ["dashboard.card"],
  });
  registerContributions(id, [
    {
      slot: "dashboard.card",
      pluginId: id,
      component: () => <div data-testid={`slot-card-${id}`}>{text}</div>,
    },
  ]);
}

beforeEach(() => {
  vi.clearAllMocks();
  resetSlotState();
});

afterEach(() => {
  resetSlotState();
});

describe("formatCents", () => {
  it("分转元并补零", () => {
    expect(formatCents(123456)).toBe("1234.56");
    expect(formatCents(5)).toBe("0.05");
    expect(formatCents(null)).toBe("—");
  });
});

describe("DashboardApp 首屏", () => {
  it("渲染设计哲学横幅与日期", async () => {
    const { dashboardApi } = await import("./api");
    vi.mocked(dashboardApi.overview).mockResolvedValue(overview);
    render(<DashboardApp />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByTestId("dashboard-root")).toBeTruthy();
    });
    expect(screen.getByText("目标导向")).toBeTruthy();
    expect(screen.getByText("AI 直接可加速过程")).toBeTruthy();
    expect(screen.getByText("过程明确化")).toBeTruthy();
    // 日期在横幅与 Today 面板各出现一次，用 getAll 断言而非 getBy
    expect(screen.getAllByText(/2026-09-18/).length).toBeGreaterThan(0);
    expect(screen.getByText(/首屏日期/)).toBeTruthy();
  });

  it("Today 面板展示日程/待办/习惯数字", async () => {
    const { dashboardApi } = await import("./api");
    vi.mocked(dashboardApi.overview).mockResolvedValue(overview);
    render(<DashboardApp />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByTestId("today-日程")).toBeTruthy();
    });
    expect(screen.getByTestId("today-日程").textContent).toBe("2");
    expect(screen.getByTestId("today-待办").textContent).toBe("3");
    expect(screen.getByTestId("today-习惯").textContent).toBe("2/4");
  });

  it("Money 面板展示总资产与净收支", async () => {
    const { dashboardApi } = await import("./api");
    vi.mocked(dashboardApi.overview).mockResolvedValue(overview);
    render(<DashboardApp />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByTestId("money-asset")).toBeTruthy();
    });
    expect(screen.getByTestId("money-asset").textContent).toBe("1234.56");
    expect(screen.getByTestId("money-net").textContent).toBe("10.00");
  });

  it("Review 面板展示 mode 与上游状态", async () => {
    const { dashboardApi } = await import("./api");
    vi.mocked(dashboardApi.overview).mockResolvedValue(overview);
    render(<DashboardApp />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByTestId("review-mode")).toBeTruthy();
    });
    expect(screen.getByTestId("review-mode").textContent).toBe("mock");
    expect(screen.getByTestId("review-online").textContent).toBe("在线");
  });

  it("Growth 占位显示空轴 + 说明", async () => {
    const { dashboardApi } = await import("./api");
    vi.mocked(dashboardApi.overview).mockResolvedValue(overview);
    render(<DashboardApp />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByTestId("growth-axes")).toBeTruthy();
    });
    expect(screen.getByTestId("growth-axes").textContent).toBe("0");
    expect(screen.getByText(/完整成长罗盘后补/)).toBeTruthy();
  });

  it("系统健康灯渲染全部模块", async () => {
    const { dashboardApi } = await import("./api");
    vi.mocked(dashboardApi.overview).mockResolvedValue(overview);
    render(<DashboardApp />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByTestId("health-calendar")).toBeTruthy();
    });
    expect(screen.getByTestId("health-todo")).toBeTruthy();
    expect(screen.getByTestId("health-habits")).toBeTruthy();
    expect(screen.getByTestId("health-agents")).toBeTruthy();
  });

  it("单模块失败：对应数字显示 —，其余照常", async () => {
    const { dashboardApi } = await import("./api");
    vi.mocked(dashboardApi.overview).mockResolvedValue(degraded);
    render(<DashboardApp />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByTestId("today-待办")).toBeTruthy();
    });
    expect(screen.getByTestId("today-待办").textContent).toBe("—");
    expect(screen.getByTestId("today-习惯").textContent).toBe("2/4");
    expect(screen.getByTestId("money-asset").textContent).toBe("—");
    expect(screen.getByText(/该模块暂不可用/)).toBeTruthy();
  });

  it("无贡献时 SlotHost 显示空态占位", async () => {
    const { dashboardApi } = await import("./api");
    vi.mocked(dashboardApi.overview).mockResolvedValue(overview);
    render(<DashboardApp />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByTestId("slot-empty")).toBeTruthy();
    });
  });

  it("SlotHost 渲染其它插件挂上来的 dashboard.card", async () => {
    const { dashboardApi } = await import("./api");
    vi.mocked(dashboardApi.overview).mockResolvedValue(overview);
    registerCardPlugin("calendar", "日程表", "日程卡片内容");
    registerCardPlugin("todo", "todo", "待办卡片内容");
    registerCardPlugin("habits", "习惯打卡", "习惯卡片内容");
    registerCardPlugin("agents", "AI 编排", "编排卡片内容");

    render(<DashboardApp />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByTestId("slot-card-calendar")).toBeTruthy();
    });
    expect(screen.getByTestId("slot-card-todo")).toBeTruthy();
    expect(screen.getByTestId("slot-card-habits")).toBeTruthy();
    expect(screen.getByTestId("slot-card-agents")).toBeTruthy();
    expect(screen.queryByTestId("slot-empty")).toBeNull();
  });

  it("overview 拉取失败显示错误与重试", async () => {
    const { dashboardApi } = await import("./api");
    vi.mocked(dashboardApi.overview).mockRejectedValue(new Error("网络不可用"));
    render(<DashboardApp />, { wrapper: makeWrapper() });
    // DashboardApp 的 useQuery 自带 retry:1，失败态要等重试耗尽
    await waitFor(
      () => {
        expect(screen.getByRole("alert")).toBeTruthy();
      },
      { timeout: 3000 },
    );
    expect(screen.getByText(/网络不可用/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "重试" })).toBeTruthy();
  });

  it("overview 只请求一次 /api/v1/dashboard/overview（经 dashboardApi）", async () => {
    const { dashboardApi } = await import("./api");
    vi.mocked(dashboardApi.overview).mockResolvedValue(overview);
    render(<DashboardApp />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByTestId("dashboard-root")).toBeTruthy();
    });
    expect(dashboardApi.overview).toHaveBeenCalled();
  });
});
