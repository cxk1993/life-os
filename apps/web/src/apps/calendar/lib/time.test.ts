import { describe, it, expect } from "vitest";
import {
  snapMinutes,
  spanDaysOf,
  segmentEvent,
  applyMove,
  applyResizeBottom,
  applyResizeRight,
  clampChild,
  hasOverlapInColumn,
  dayIndexInWeek,
  addDays,
  DAY_MS,
  formatSH,
  shMonday,
  shWallClock,
} from "./time";

// 2026-09-14 周一（作为周起始）；2026-09-15 周二
const MON = new Date(2026, 8, 14, 0, 0, 0);
const TUE_08 = new Date(2026, 8, 15, 8, 0, 0);
const TUE_10 = new Date(2026, 8, 15, 10, 0, 0);
const FRI_20 = new Date(2026, 8, 18, 20, 0, 0);
const SAT_02 = new Date(2026, 8, 19, 2, 0, 0);
const bounds = { weekStart: MON, weekDays: 7 };

describe("snapMinutes", () => {
  it("吸附到最近的 30 分钟", () => {
    expect(snapMinutes(7)).toBe(0);
    expect(snapMinutes(18)).toBe(30);
    expect(snapMinutes(45)).toBe(60);
    expect(snapMinutes(70)).toBe(60);
    expect(snapMinutes(80)).toBe(90);
  });
});

describe("spanDaysOf", () => {
  it("单日事件 = 1", () => {
    expect(spanDaysOf(TUE_08, TUE_10)).toBe(1);
  });
  it("跨天事件（周五20 → 周六02）计 2 天", () => {
    expect(spanDaysOf(FRI_20, SAT_02)).toBe(2);
  });
});

describe("segmentEvent 跨天拆分", () => {
  it("周五20→周六02 拆成两段连续片段", () => {
    const segs = segmentEvent(FRI_20, SAT_02, MON);
    expect(segs).toHaveLength(2);
    expect(segs[0].dayIndex).toBe(dayIndexInWeek(FRI_20, MON)); // 周五 = 列4
    expect(segs[1].dayIndex).toBe(dayIndexInWeek(SAT_02, MON)); // 周六 = 列5
    // 第一段从 20:00 到当天 24:00
    expect(segs[0].start.getHours()).toBe(20);
    expect(segs[0].end.getHours()).toBe(0);
    expect(segs[0].isFirst).toBe(true);
    expect(segs[1].isLast).toBe(true);
  });
});

describe("applyMove 钳制", () => {
  it("整块在周内自由移动（吸附值已给）", () => {
    const r = applyMove(TUE_08, TUE_10, 1, 0.5, bounds);
    expect(r.start.getDay()).toBe(3); // 周三
    expect(r.start.getHours()).toBe(8);
    expect(r.start.getMinutes()).toBe(30);
  });
  it("左移越界被钳制回周一起始", () => {
    const r = applyMove(TUE_08, TUE_10, -10, 0, bounds);
    // 起点被钳制到周一 00:00
    expect(r.start.getTime()).toBe(MON.getTime());
  });
  it("右移越界被钳制回周日 24:00 之前", () => {
    const sundayEnd = addDays(MON, 7);
    // 把一个事件放到周六，再右移很多天，end 不能超过周日末
    const r = applyMove(
      new Date(2026, 8, 19, 20, 0, 0),
      new Date(2026, 8, 19, 22, 0, 0),
      10,
      0,
      bounds,
    );
    expect(r.end.getTime()).toBeLessThanOrEqual(sundayEnd.getTime());
  });
});

describe("applyResizeBottom 最短 30 分钟、不跨天", () => {
  it("缩短到小于 30 分钟被钳制为 30 分钟", () => {
    const r = applyResizeBottom(TUE_08, TUE_10, -10, 30); // 想缩短600分钟
    const durMin = (r.end.getTime() - r.start.getTime()) / 60000;
    expect(durMin).toBe(30);
  });
  it("拉长不越过当日 24:00", () => {
    const late = new Date(2026, 8, 15, 23, 30, 0);
    const r = applyResizeBottom(late, new Date(2026, 8, 15, 23, 45, 0), 5, 30);
    expect(r.end.getHours()).toBe(0); // 钳制到次日00:00前（即当天24:00）
  });
});

describe("applyResizeRight 跨天", () => {
  it("右缘拉 1 天 → spanDays +1", () => {
    const r = applyResizeRight(TUE_08, TUE_10, 1, bounds, 30);
    expect(spanDaysOf(r.start, r.end)).toBe(2);
  });
  it("越界被钳制在周内", () => {
    const sundayEnd = addDays(MON, 7);
    const r = applyResizeRight(
      new Date(2026, 8, 19, 20, 0, 0),
      new Date(2026, 8, 19, 22, 0, 0),
      10,
      bounds,
      30,
    );
    expect(r.end.getTime()).toBeLessThanOrEqual(sundayEnd.getTime());
  });
});

describe("clampChild 子块不越父块", () => {
  it("完全在父外的子块被拉回父起点", () => {
    const parent = { s: TUE_08, e: TUE_10 }; // 09:00-12:00
    const child = { s: new Date(2026, 8, 15, 0, 0, 0), e: new Date(2026, 8, 15, 2, 0, 0) };
    const r = clampChild(parent.s, parent.e, child.s, child.e);
    expect(r.start.getTime()).toBe(parent.s.getTime());
    expect(r.end.getTime()).toBeLessThanOrEqual(parent.e.getTime());
  });
  it("比父还长的子块被截断为父跨度", () => {
    const parent = { s: TUE_08, e: TUE_10 }; // 2h
    const child = { s: TUE_08, e: addDays(TUE_08, 1) }; // 24h
    const r = clampChild(parent.s, parent.e, child.s, child.e);
    expect(r.start.getTime()).toBe(parent.s.getTime());
    expect(r.end.getTime()).toBe(parent.e.getTime());
  });
  it("正常范围内的子块保持原样", () => {
    const TUE_12 = new Date(2026, 8, 15, 12, 0, 0);
    const parent = { s: TUE_08, e: TUE_12 }; // 08:00-12:00
    const child = { s: new Date(2026, 8, 15, 9, 0, 0), e: new Date(2026, 8, 15, 11, 0, 0) };
    const r = clampChild(parent.s, parent.e, child.s, child.e);
    expect(r.start.getHours()).toBe(9);
    expect(r.end.getHours()).toBe(11);
  });
});

describe("hasOverlapInColumn", () => {
  it("相邻不重叠 → false", () => {
    expect(
      hasOverlapInColumn([
        { start: TUE_08, end: TUE_10 },
        { start: new Date(2026, 8, 15, 10, 0, 0), end: new Date(2026, 8, 15, 12, 0, 0) },
      ]),
    ).toBe(false);
  });
  it("部分重叠 → true", () => {
    expect(
      hasOverlapInColumn([
        { start: TUE_08, end: TUE_10 },
        { start: new Date(2026, 8, 15, 9, 30, 0), end: new Date(2026, 8, 15, 11, 0, 0) },
      ]),
    ).toBe(true);
  });
});

describe("东八区窗口助手（formatSH / shMonday）", () => {
  it("shWallClock(2026,9,14) 的 formatSH 带 +08:00 且为当日 00:00", () => {
    expect(formatSH(shWallClock(2026, 9, 14, 0, 0, 0, 0))).toBe("2026-09-14T00:00:00.000+08:00");
  });
  it("shMonday 取回本周一（东八区）", () => {
    // 2026-09-16 周三（UTC 00:00）在东八区是 09-16 08:00，周一应为 09-14
    const mon = shMonday(new Date(Date.UTC(2026, 8, 16, 0, 0, 0)));
    expect(mon.getTime()).toBe(shWallClock(2026, 9, 14, 0, 0, 0, 0).getTime());
  });
  it("周窗口 from→to 恰好 7 天且都带 +08:00", () => {
    const mon = shMonday(new Date(Date.UTC(2026, 8, 16, 0, 0, 0)));
    const from = formatSH(mon);
    const to = formatSH(new Date(mon.getTime() + 7 * DAY_MS));
    expect(from).toBe("2026-09-14T00:00:00.000+08:00");
    expect(to).toBe("2026-09-21T00:00:00.000+08:00");
  });
});
