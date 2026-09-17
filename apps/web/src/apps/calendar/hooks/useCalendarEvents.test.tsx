import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useCalendarEvents, applyOptimisticMove } from "./useCalendarEvents";
import { calendarApi } from "../api";

const FROM = "2026-09-14T00:00:00+08:00";
const TO = "2026-09-21T00:00:00+08:00";

vi.mock("../api", () => {
  const base = (id: string) => ({
    id,
    title: id,
    color: "var(--accent)",
    start_at: "2026-09-15T08:00:00+08:00",
    end_at: "2026-09-15T09:00:00+08:00",
    all_day: false,
    span_days: 1,
    source: "manual",
    parent_id: null,
    sort: 0,
    location: null,
    note: null,
    children: [],
  });
  return {
    calendarApi: {
      listRange: vi.fn().mockResolvedValue([base("a"), base("b")]),
      update: vi.fn(),
      create: vi.fn(),
      remove: vi.fn(),
      addChild: vi.fn(),
      updateChild: vi.fn(),
      removeChild: vi.fn(),
      freeSlots: vi.fn().mockResolvedValue([]),
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

beforeEach(() => {
  vi.mocked(calendarApi.listRange).mockResolvedValue([
    {
      id: "a",
      title: "a",
      color: "var(--accent)",
      start_at: "2026-09-15T08:00:00+08:00",
      end_at: "2026-09-15T09:00:00+08:00",
      all_day: false,
      span_days: 1,
      source: "manual",
      parent_id: null,
      sort: 0,
      location: null,
      note: null,
      children: [],
    },
    {
      id: "b",
      title: "b",
      color: "var(--accent)",
      start_at: "2026-09-15T10:00:00+08:00",
      end_at: "2026-09-15T11:00:00+08:00",
      all_day: false,
      span_days: 1,
      source: "manual",
      parent_id: null,
      sort: 0,
      location: null,
      note: null,
      children: [],
    },
  ]);
});

describe("useCalendarEvents", () => {
  it("加载并渲染事件", async () => {
    const { result } = renderHook(() => useCalendarEvents({ from: FROM, to: TO }), {
      wrapper: makeWrapper(),
    });
    await waitFor(() => expect(result.current.events.length).toBe(2));
  });

  it("更新失败 → 乐观更新后回滚", async () => {
    // 延迟拒绝，让乐观态在回滚前可被观察
    vi.mocked(calendarApi.update).mockImplementation(
      () =>
        new Promise((_, rej) => {
          setTimeout(() => rej(new Error("boom")), 80);
        }),
    );
    const { result } = renderHook(() => useCalendarEvents({ from: FROM, to: TO }), {
      wrapper: makeWrapper(),
    });
    await waitFor(() => expect(result.current.events.length).toBe(2));

    act(() => {
      result.current.updateEvent.mutate({
        id: "a",
        patch: { start_at: "2026-09-15T10:00:00+08:00" },
      });
    });
    // 乐观：立即把 a 的起点改成 10:00（+08:00 等价于 02:00Z，按时间比较避免时区串格式差异）
    const want10 = new Date("2026-09-15T10:00:00+08:00").getTime();
    await waitFor(() =>
      expect(new Date(result.current.events.find((e) => e.id === "a")!.start_at).getTime()).toBe(
        want10,
      ),
    );
    // 失败：回滚到 08:00
    const want08 = new Date("2026-09-15T08:00:00+08:00").getTime();
    await waitFor(() =>
      expect(new Date(result.current.events.find((e) => e.id === "a")!.start_at).getTime()).toBe(
        want08,
      ),
    );
  });

  it("applyOptimisticMove 平移整棵子树（父块移动子块跟随）", () => {
    const child = {
      id: "a1",
      title: "a1",
      color: "var(--accent)",
      start_at: "2026-09-15T09:00:00+08:00",
      end_at: "2026-09-15T09:30:00+08:00",
      all_day: false,
      span_days: 1,
      source: "manual",
      parent_id: "a",
      sort: 0,
      location: null,
      note: null,
      children: [],
    };
    const parent = {
      id: "a",
      title: "a",
      color: "var(--accent)",
      start_at: "2026-09-15T08:00:00+08:00",
      end_at: "2026-09-15T09:00:00+08:00",
      all_day: false,
      span_days: 1,
      source: "manual",
      parent_id: null,
      sort: 0,
      location: null,
      note: null,
      children: [child],
    };
    const out = applyOptimisticMove([parent], "a", {
      start_at: "2026-09-15T10:00:00+08:00",
    });
    expect(new Date(out[0].start_at).getTime()).toBe(
      new Date("2026-09-15T10:00:00+08:00").getTime(),
    );
    expect(new Date(out[0].children[0].start_at).getTime()).toBe(
      new Date("2026-09-15T11:00:00+08:00").getTime(),
    );
  });

  it("创建成功 → 合并进缓存", async () => {
    vi.mocked(calendarApi.create).mockResolvedValue({
      id: "c",
      title: "新事项",
      color: "var(--accent)",
      start_at: "2026-09-15T12:00:00+08:00",
      end_at: "2026-09-15T13:00:00+08:00",
      all_day: false,
      span_days: 1,
      source: "manual",
      parent_id: null,
      sort: 0,
      location: null,
      note: null,
      children: [],
    });
    const { result } = renderHook(() => useCalendarEvents({ from: FROM, to: TO }), {
      wrapper: makeWrapper(),
    });
    await waitFor(() => expect(result.current.events.length).toBe(2));

    act(() => {
      result.current.createEvent.mutate({
        title: "新事项",
        start_at: "2026-09-15T12:00:00+08:00",
        end_at: "2026-09-15T13:00:00+08:00",
      });
    });
    await waitFor(() => expect(result.current.events.find((e) => e.id === "c")).toBeTruthy());
  });
});
