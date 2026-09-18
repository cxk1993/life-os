/** 习惯打卡前端测试。网络全 mock。 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import HabitsApp from "./HabitsApp";
import HabitRow from "./HabitRow";
import DashboardCard from "./slots/DashboardCard";
import type { Habit } from "./api";

const habit: Habit = {
  id: "h1",
  name: "早睡",
  target: "23:30 前",
  rule: { type: "daily" },
  color: "var(--accent)",
  reminder_time: "",
  rest_weekdays: [5, 6],
  archived: false,
  sort: 0,
  today_status: "pending",
  streak: 3,
  created_at: "2026-09-17T00:00:00+00:00",
  updated_at: "2026-09-17T00:00:00+00:00",
};

vi.mock("@/shared/api/events", () => ({
  usePluginEvent: () => {},
}));

vi.mock("./api", () => ({
  habitsApi: {
    list: vi.fn().mockResolvedValue([]),
    create: vi.fn().mockResolvedValue({ id: "new", name: "x" }),
    update: vi.fn().mockResolvedValue({ id: "h1", archived: true }),
    remove: vi.fn().mockResolvedValue(undefined),
    checkin: vi.fn().mockResolvedValue({}),
    uncheck: vi.fn().mockResolvedValue({}),
    summary: vi.fn().mockResolvedValue({ total: 0, done: 0, pending: 0, rest: 0, best_streak: 0 }),
  },
}));

function makeWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

function renderRow(h: Habit) {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <HabitRow habit={h} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("HabitsApp 冒烟", () => {
  it("空态显示添加入口", async () => {
    render(<HabitsApp />, { wrapper: makeWrapper() });
    expect(screen.getByLabelText("添加习惯")).toBeTruthy();
    expect(screen.getByRole("button", { name: "添加" })).toBeTruthy();
  });

  it("输入后提交 create", async () => {
    const { habitsApi } = await import("./api");
    render(<HabitsApp />, { wrapper: makeWrapper() });
    const input = screen.getByLabelText("添加习惯");
    fireEvent.change(input, { target: { value: "晨跑" } });
    fireEvent.click(screen.getByRole("button", { name: "添加" }));
    await waitFor(() => {
      expect(habitsApi.create).toHaveBeenCalledWith({ name: "晨跑" });
    });
  });

  it("列表渲染习惯与今日进度", async () => {
    const { habitsApi } = await import("./api");
    const doneHabit: Habit = { ...habit, id: "h2", name: "冥想", today_status: "done", streak: 5 };
    vi.mocked(habitsApi.list).mockResolvedValue([habit, doneHabit]);
    render(<HabitsApp />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByText("早睡")).toBeTruthy();
      expect(screen.getByText("冥想")).toBeTruthy();
    });
    expect(screen.getByText(/今日 1\/2/)).toBeTruthy();
  });

  it("今日状态：done 显示勾，rest 显示休", async () => {
    const { habitsApi } = await import("./api");
    vi.mocked(habitsApi.list).mockResolvedValue([
      { ...habit, id: "h1", name: "已打卡", today_status: "done" },
      { ...habit, id: "h2", name: "休息日", today_status: "rest", streak: 0 },
    ]);
    render(<HabitsApp />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "取消打卡 已打卡" })).toBeTruthy();
    });
    expect(screen.getByRole("button", { name: "打卡 休息日" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "打卡 休息日" }).textContent).toBe("休");
    expect(screen.getByRole("button", { name: "取消打卡 已打卡" }).textContent).toBe("✓");
  });
});

describe("HabitRow", () => {
  it("渲染名称、目标、连击", () => {
    renderRow(habit);
    expect(screen.getByText("早睡")).toBeTruthy();
    expect(screen.getByText("23:30 前")).toBeTruthy();
    expect(screen.getByText(/连续 3 天/)).toBeTruthy();
    expect(screen.getByText(/休/)).toBeTruthy();
  });

  it("点击打卡按钮调用 checkin", async () => {
    const { habitsApi } = await import("./api");
    renderRow(habit);
    fireEvent.click(screen.getByRole("button", { name: "打卡 早睡" }));
    await waitFor(() => {
      expect(habitsApi.checkin).toHaveBeenCalledWith("h1");
    });
  });

  it("已完成时点击调用 uncheck", async () => {
    const { habitsApi } = await import("./api");
    renderRow({ ...habit, today_status: "done" });
    fireEvent.click(screen.getByRole("button", { name: "取消打卡 早睡" }));
    await waitFor(() => {
      expect(habitsApi.uncheck).toHaveBeenCalled();
    });
  });

  it("归档按钮调用 update archived=true", async () => {
    const { habitsApi } = await import("./api");
    renderRow(habit);
    fireEvent.click(screen.getByRole("button", { name: "归档 早睡" }));
    await waitFor(() => {
      expect(habitsApi.update).toHaveBeenCalledWith("h1", { archived: true });
    });
  });

  it("删除需 confirm，确认后调用 remove", async () => {
    const { habitsApi } = await import("./api");
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    renderRow(habit);
    fireEvent.click(screen.getByRole("button", { name: "删除 早睡" }));
    await waitFor(() => {
      expect(habitsApi.remove).toHaveBeenCalledWith("h1");
    });
    confirmSpy.mockRestore();
  });

  it("streak=0 时不显示连续天数", () => {
    renderRow({ ...habit, streak: 0 });
    expect(screen.queryByText(/连续/)).toBeNull();
  });
});

describe("DashboardCard", () => {
  it("空数据显示占位", async () => {
    render(<DashboardCard />, { wrapper: makeWrapper() });
    expect(screen.getByText("习惯")).toBeTruthy();
    await waitFor(() => {
      expect(screen.getByText("还没有习惯")).toBeTruthy();
    });
  });

  it("有 summary 时展示今日完成与最长连击", async () => {
    const { habitsApi } = await import("./api");
    vi.mocked(habitsApi.summary).mockResolvedValue({
      total: 4,
      done: 2,
      pending: 1,
      rest: 1,
      best_streak: 12,
    });
    render(<DashboardCard />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByText("2/4")).toBeTruthy();
    });
    expect(screen.getByText("12")).toBeTruthy();
  });
});
