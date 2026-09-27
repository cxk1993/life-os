/**
 * 日程待办容器冒烟测试（主人 2026-09-25 令「todo×日程合并」· 总监令 10 §2 判据④）。
 *
 * 验证：①四页签齐（日程表/待办/学业/课程表）②默认停在日程表 ③切页 aria-selected+面板显隐
 * ④默认页挂载日程表内容（懒挂载：待办未点前不挂载）。
 * 子 App 用桩替身——真实 App 的渲染由各自测试管辖，本测不重复、不冒充。
 */
import { render, screen, fireEvent } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// mock 形态对齐真实模块：CalendarApp 命名导出 / TodoApp、StudyApp、CourseApp default 导出。
vi.mock("../calendar/CalendarApp", () => ({
  CalendarApp: () => <div data-testid="stub-calendar">日程表桩</div>,
}));
vi.mock("../todo/TodoApp", () => ({
  default: () => <div data-testid="stub-todo">待办桩</div>,
}));
vi.mock("../study/StudyApp", () => ({
  default: () => <div data-testid="stub-study">学业桩</div>,
}));
vi.mock("../course/CourseApp", () => ({
  default: () => <div data-testid="stub-course">课程表桩</div>,
}));

import ScheduleApp from "./ScheduleApp";

// MultitabFrame 有 persistKey 页签记忆（localStorage）——每例前清掉，
// 保证「默认页」断言测的是容器装配而非上一例残留状态。
beforeEach(() => {
  localStorage.clear();
});

describe("ScheduleApp（日程待办学业课程表四页容器）", () => {
  it("渲染四页签：日程表 / 待办 / 学业 / 课程表，默认选中日程表", () => {
    // ★ 2026-09-26 更新（astrbot · 主人令「学业页」）：容器由两页扩为三页。
    // ★ 2026-09-27 更新（hermes · 主人令「加一页课程表」）：容器扩为四页。
    render(<ScheduleApp />);
    const tabs = screen.getAllByRole("tab");
    expect(tabs).toHaveLength(4);
    expect(tabs[0].textContent).toContain("日程表");
    expect(tabs[1].textContent).toContain("待办");
    expect(tabs[2].textContent).toContain("学业");
    expect(tabs[3].textContent).toContain("课程表");
    expect(tabs[0].getAttribute("aria-selected")).toBe("true");
  });

  it("切到待办页签后面板成为当前，日程表面板隐藏", async () => {
    render(<ScheduleApp />);
    await screen.findByTestId("stub-calendar");
    fireEvent.click(screen.getByTestId("mtab-tab-todo"));
    expect(screen.getByTestId("mtab-tab-todo").getAttribute("aria-selected")).toBe("true");
    expect(screen.getByTestId("mtab-panel-todo").hidden).toBe(false);
    expect(screen.getByTestId("mtab-panel-calendar").hidden).toBe(true);
    expect(await screen.findByTestId("stub-todo")).toBeTruthy();
  });

  it("★ 切到课程表页签 → 课程表页成为当前并挂载", async () => {
    render(<ScheduleApp />);
    await screen.findByTestId("stub-calendar");
    fireEvent.click(screen.getByTestId("mtab-tab-course"));
    expect(screen.getByTestId("mtab-tab-course").getAttribute("aria-selected")).toBe("true");
    expect(screen.getByTestId("mtab-panel-course").hidden).toBe(false);
    expect(await screen.findByTestId("stub-course")).toBeTruthy();
  });

  it("默认页挂载日程表内容（懒挂载：待办未点前不挂载）", async () => {
    render(<ScheduleApp />);
    expect(await screen.findByTestId("stub-calendar")).toBeTruthy();
    expect(screen.queryByTestId("stub-todo")).toBeNull();
  });
});
