/**
 * 课程表主视图测试（2026-09-27 · 主人令「日程待办加一页课程表」）。
 *
 * 钉住：①周网格 7 列（周一…周日）渲染；②课程卡片显示课名/时间/地点；
 *       ③点「+ 加课」打开表单；④空课表给引导文案。
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CourseApp from "./CourseApp";

const weekMock = vi.fn();
const createMock = vi.fn();
const schedMock = vi.fn();

vi.mock("./api", async () => {
  const actual = await vi.importActual<typeof import("./api")>("./api");
  return {
    ...actual,
    courseApi: {
      week: (...a: unknown[]) => weekMock(...a),
      create: (...a: unknown[]) => createMock(...a),
      update: vi.fn(),
      remove: vi.fn(),
      list: vi.fn(),
    },
  };
});

vi.mock("@/shared/api/client", () => {
  class ApiError extends Error {
    status = 500;
    detail = "";
    title = "";
  }
  return {
    ApiError,
    api: {
      get: (...a: unknown[]) => schedMock(...a),
    },
  };
});

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

function gridWith(course: Record<string, unknown>) {
  return {
    term_start: null,
    term_week: null,
    days: ["周一", "周二", "周三", "周四", "周五", "周六", "周日"].map((label, i) => ({
      weekday: i,
      label,
      items: i === 0 ? [course] : [],
    })),
  };
}

describe("CourseApp（课程表周网格）", () => {
  beforeEach(() => {
    weekMock.mockReset();
    createMock.mockReset();
    schedMock.mockReset();
    schedMock.mockResolvedValue({ enabled: false, running: false, lead_minutes: 15 });
  });

  it("① 周网格渲染 7 列（周一…周日）", async () => {
    weekMock.mockResolvedValue(gridWith({
      id: "c1", name: "高等数学", teacher: "张老师", location: "知新楼 B203",
      weekday: 0, start_section: 1, end_section: 2, start_time: "08:00", end_time: "09:40",
      weeks: "1-16", term_start: null, note: null, enabled: true, sort: 0,
      created_at: "2026-09-27T00:00:00+08:00", updated_at: "2026-09-27T00:00:00+08:00",
    }));
    const { container } = render(<CourseApp />, { wrapper });
    await waitFor(() => expect(container.querySelector("[data-testid='course-grid']")).toBeTruthy());
    expect(container.querySelectorAll(".course-col")).toHaveLength(7);
  });

  it("② 课程卡片显示课名 / 时间 / 地点", async () => {
    weekMock.mockResolvedValue(gridWith({
      id: "c1", name: "高等数学", teacher: "张老师", location: "知新楼 B203",
      weekday: 0, start_section: 1, end_section: 2, start_time: "08:00", end_time: "09:40",
      weeks: "1-16", term_start: null, note: null, enabled: true, sort: 0,
      created_at: "2026-09-27T00:00:00+08:00", updated_at: "2026-09-27T00:00:00+08:00",
    }));
    render(<CourseApp />, { wrapper });
    expect(await screen.findByText("高等数学")).toBeTruthy();
    expect(screen.getByText("08:00–09:40")).toBeTruthy();
    expect(screen.getByText("知新楼 B203 · 张老师")).toBeTruthy();
    expect(screen.getByText("周次 1-16")).toBeTruthy();
  });

  it("③ 点「+ 加课」打开表单", async () => {
    weekMock.mockResolvedValue(gridWith({
      id: "c1", name: "大学物理", teacher: null, location: null,
      weekday: 0, start_section: null, end_section: null, start_time: null, end_time: null,
      weeks: null, term_start: null, note: null, enabled: true, sort: 0,
      created_at: "2026-09-27T00:00:00+08:00", updated_at: "2026-09-27T00:00:00+08:00",
    }));
    render(<CourseApp />, { wrapper });
    fireEvent.click(await screen.findByTestId("course-add"));
    expect(await screen.findByLabelText("课名 *")).toBeTruthy();
    expect(screen.getByLabelText("地点")).toBeTruthy();
    expect(screen.getByLabelText(/周次/)).toBeTruthy();
  });

  it("④ 空课表给引导文案", async () => {
    weekMock.mockResolvedValue({
      term_start: null, term_week: null,
      days: ["周一", "周二", "周三", "周四", "周五", "周六", "周日"].map((label, i) => ({
        weekday: i, label, items: [],
      })),
    });
    render(<CourseApp />, { wrapper });
    expect(await screen.findByText("还没有课程")).toBeTruthy();
  });
});
