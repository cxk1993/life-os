/**
 * 课程表主视图测试（2026-09-27 · 主人令「日程待办加一页课程表」）。
 *
 * 钉住：
 *   ① 节次 × 星期 网格（纵轴 = 节次，横轴 = 周一…周日）；
 *   ② 课程卡片显示课名 / 时间 / 地点 / 周次；
 *   ③ 点「+ 加课」打开表单（含节次字段）；
 *   ④ 「学期设置」入口 + 第 N 教学周显示；
 *   ⑤ 空课表给引导文案。
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CourseApp from "./CourseApp";

const weekMock = vi.fn();
const createMock = vi.fn();
const schedMock = vi.fn();
const setTermMock = vi.fn();

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
      getTerm: vi.fn(),
      setTerm: (...a: unknown[]) => setTermMock(...a),
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

const SECTIONS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12];

function gridWith(items: Record<string, unknown>[] = []) {
  return {
    term_start: null,
    term_week: null,
    sections: SECTIONS,
    today_weekday: 0,
    days: ["周一", "周二", "周三", "周四", "周五", "周六", "周日"].map((label, i) => ({
      weekday: i,
      label,
      items: i === 0 ? items : [],
    })),
  };
}

const MATH = {
  id: "c1",
  name: "高等数学",
  teacher: "张老师",
  location: "知新楼 B203",
  weekday: 0,
  start_section: 1,
  end_section: 2,
  start_time: "08:00",
  end_time: "09:40",
  weeks: "1-16",
  term_start: null,
  note: null,
  enabled: true,
  sort: 0,
  created_at: "2026-09-27T00:00:00+08:00",
  updated_at: "2026-09-27T00:00:00+08:00",
};

describe("CourseApp（节次 × 星期 网格）", () => {
  beforeEach(() => {
    weekMock.mockReset();
    createMock.mockReset();
    schedMock.mockReset();
    setTermMock.mockReset();
    schedMock.mockResolvedValue({ enabled: false, running: false, lead_minutes: 30 });
  });

  it("① 渲染节次纵轴（12 行）+ 7 个星期表头", async () => {
    weekMock.mockResolvedValue(gridWith([MATH]));
    const { container } = render(<CourseApp />, { wrapper });
    await waitFor(() => expect(container.querySelector("[data-testid='course-grid']")).toBeTruthy());
    // 纵轴节次行 = sections 条数
    expect(container.querySelectorAll(".course-row")).toHaveLength(SECTIONS.length);
    // 表头 = 角落 + 7 天
    expect(container.querySelectorAll(".course-hcell")).toHaveLength(8);
    expect(container.querySelectorAll(".course-sec")).toHaveLength(SECTIONS.length);
    // 行内含 7 个格子
    expect(container.querySelectorAll(".course-cell").length).toBe(SECTIONS.length * 7);
  });

  it("② 课程卡片显示课名 / 时间 / 地点 / 周次", async () => {
    weekMock.mockResolvedValue(gridWith([MATH]));
    render(<CourseApp />, { wrapper });
    expect(await screen.findByText("高等数学")).toBeTruthy();
    expect(screen.getByText("08:00–09:40")).toBeTruthy();
    expect(screen.getByText("知新楼 B203 · 张老师")).toBeTruthy();
    expect(screen.getByText("周次 1-16")).toBeTruthy();
  });

  it("③ 点「+ 加课」打开表单（含节次字段）", async () => {
    weekMock.mockResolvedValue(gridWith([MATH]));
    render(<CourseApp />, { wrapper });
    fireEvent.click(await screen.findByTestId("course-add"));
    expect(await screen.findByLabelText("课名 *")).toBeTruthy();
    expect(screen.getByLabelText("起始节次")).toBeTruthy();
    expect(screen.getByLabelText("结束节次")).toBeTruthy();
    expect(screen.getByLabelText("地点")).toBeTruthy();
    expect(screen.getByLabelText(/周次/)).toBeTruthy();
  });

  it("④ 学期设置入口可开（含第一周周一字段）", async () => {
    weekMock.mockResolvedValue({ ...gridWith([MATH]), term_start: "2026-09-01", term_week: 4 });
    render(<CourseApp />, { wrapper });
    expect(await screen.findByText(/第 4 教学周/)).toBeTruthy();
    fireEvent.click(screen.getByTestId("course-term"));
    expect(await screen.findByTestId("course-term-input")).toBeTruthy();
  });

  it("⑤ 空课表给引导文案", async () => {
    weekMock.mockResolvedValue(gridWith([]));
    render(<CourseApp />, { wrapper });
    expect(await screen.findByText("还没有课程")).toBeTruthy();
  });
});
