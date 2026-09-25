/**
 * V8 · FullCalendar 原型测试（对照表 v1）。
 * - toEventInputs：CalendarEvent → EventInput 映射（id/title/start/end/allDay/color/classNames）；
 * - toFullCalView：日/周/月 → timeGridDay/timeGridWeek/dayGridMonth；
 * - argToSpan：拖拽/缩放回调 → start/end/spanDays；
 * - 冒烟：FullCalendar 容器渲染（jsdom 下 FullCalendar 可挂载 DOM）。
 */
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import FullCalView, { toEventInputs, toFullCalView, argToSpan, renderBadge } from "./FullCalView";
import type { CalendarEvent } from "../api";

const ev = (id: string, over: Partial<CalendarEvent> = {}): CalendarEvent => ({
  id,
  title: `事项${id}`,
  color: "var(--accent)",
  start_at: "2026-09-24T02:00:00.000Z",
  end_at: "2026-09-24T03:00:00.000Z",
  all_day: false,
  span_days: 1,
  source: "manual",
  parent_id: null,
  sort: 0,
  location: null,
  note: null,
  children: [],
  ...over,
});

describe("V8 FullCalendar 原型", () => {
  it("toEventInputs 映射：id/title/start/end/allDay/color/classNames", () => {
    const inputs = toEventInputs([
      ev("a"),
      ev("b", { parent_id: "a", all_day: true, color: "#ff6600" }),
    ]);
    expect(inputs).toHaveLength(2);
    expect(inputs[0]).toMatchObject({
      id: "a",
      title: "事项a",
      start: "2026-09-24T02:00:00.000Z",
      end: "2026-09-24T03:00:00.000Z",
      allDay: false,
      backgroundColor: "var(--accent)",
    });
    // 子块带 classNames（视觉区分）
    expect(inputs[1].classNames).toEqual(["fc-event--child"]);
    expect(inputs[1].extendedProps?.parent_id).toBe("a");
    expect(inputs[1].allDay).toBe(true);
  });

  it("toFullCalView 映射：日/周/月 → FullCalendar 视图名", () => {
    expect(toFullCalView("day")).toBe("timeGridDay");
    expect(toFullCalView("week")).toBe("timeGridWeek");
    expect(toFullCalView("month")).toBe("dayGridMonth");
  });

  it("argToSpan：回调事件 → start/end/spanDays（缺省 span 按时长算）", () => {
    const arg = {
      event: {
        id: "a",
        start: new Date("2026-09-24T02:00:00.000Z"),
        end: new Date("2026-09-26T02:00:00.000Z"),
        extendedProps: { span_days: 2 },
      },
    } as unknown as Parameters<typeof argToSpan>[0];
    const r = argToSpan(arg);
    expect(r.start).toBe("2026-09-24T02:00:00.000Z");
    expect(r.end).toBe("2026-09-26T02:00:00.000Z");
    expect(r.spanDays).toBe(2);
  });

  it("renderBadge：父块徽标（V8 v2 判据1）", () => {
    expect(renderBadge(0)).toBe("");
    expect(renderBadge(3)).toContain("子块");
    expect(renderBadge(3)).toContain("3");
    // toEventInputs 带 children 数
    const inputs = toEventInputs([ev("p", { children: [ev("c1"), ev("c2")] })]);
    expect(inputs[0].extendedProps?.children_count).toBe(2);
  });

  it("冒烟：FullCalendar 容器渲染（view=week）", () => {
    const { container } = render(
      <FullCalView
        events={[ev("a")]}
        view="week"
        anchor={new Date("2026-09-24T00:00:00+08:00")}
        onMove={() => undefined}
        onResize={() => undefined}
        onCreateAt={() => undefined}
        onSelect={() => undefined}
        onRangeChange={() => undefined}
      />,
    );
    expect(container.querySelector('[data-testid="fullcal-view"]')).toBeTruthy();
  });
});
