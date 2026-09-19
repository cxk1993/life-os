import { describe, it, expect } from "vitest";
import {
  SNAP_MIN,
  snapMinutes,
  snapToGrid,
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
const TUE_12 = new Date(2026, 8, 15, 12, 0, 0);
const FRI_20 = new Date(2026, 8, 18, 20, 0, 0);
const SAT_02 = new Date(2026, 8, 19, 2, 0, 0);
const bounds = { weekStart: MON, weekDays: 7 };

describe("snapMinutes", () => {
  it("吸附到最近的 15 分钟（T27 卡要求）", () => {
    expect(snapMinutes(7)).toBe(0);
    expect(snapMinutes(18)).toBe(15);
    expect(snapMinutes(45)).toBe(45);
    expect(snapMinutes(70)).toBe(75);
    expect(snapMinutes(80)).toBe(75);
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

// ───────────────────────── T27 增补：15 分钟吸附 + 嵌套 clamp 边界 ─────────────────────────
describe("T27 · 15 分钟吸附粒度", () => {
  it("snapMinutes 按 15 分钟网格（含半格偏移）", () => {
    expect(SNAP_MIN).toBe(15);
    expect(snapMinutes(0)).toBe(0);
    expect(snapMinutes(14)).toBe(15);
    expect(snapMinutes(16)).toBe(15);
    expect(snapMinutes(22)).toBe(15);
    expect(snapMinutes(23)).toBe(30);
    expect(snapMinutes(37)).toBe(30); // 37 距 30=7、距 45=8 → 30
    expect(snapMinutes(38)).toBe(45); // 38 距 45=7 → 45
    expect(snapMinutes(52)).toBe(45); // 52 距 45=7 → 45
    expect(snapMinutes(53)).toBe(60); // 53 距 60=7 → 60
  });
  it("snapToGrid 把时刻吸附到最近 15 分钟", () => {
    const dayStart = shWallClock(2026, 9, 14, 0, 0, 0, 0); // 周一 00:00
    // 09:07 → 09:00（7<7.5）
    const r1 = snapToGrid(
      new Date(dayStart.getTime() + 9 * 60 * 60 * 1000 + 7 * 60 * 1000),
      dayStart,
    );
    expect(r1.getHours()).toBe(9);
    expect(r1.getMinutes()).toBe(0);
    // 09:08 → 09:15（8>7.5）
    const r2 = snapToGrid(
      new Date(dayStart.getTime() + 9 * 60 * 60 * 1000 + 8 * 60 * 1000),
      dayStart,
    );
    expect(r2.getHours()).toBe(9);
    expect(r2.getMinutes()).toBe(15);
  });
});

describe("T27 · 嵌套 clamp 边界（子块拖/拉越界不产生孤儿块）", () => {
  const parent = { s: TUE_08, e: TUE_12 }; // 08:00–12:00

  it("子块下边缘越出父块 → 整体上移保持时长（不截断、不越界）", () => {
    // 子块 11:00–13:00：越出父块下界 1h，时长 2h
    const child = { s: new Date(2026, 8, 15, 11, 0, 0), e: new Date(2026, 8, 15, 13, 0, 0) };
    const r = clampChild(parent.s, parent.e, child.s, child.e);
    // 实现语义：时长保留、整体平移回父块内 → 10:00–12:00
    expect(r.start.getHours()).toBe(10);
    expect(r.end.getTime()).toBe(parent.e.getTime());
    expect(r.end.getTime() - r.start.getTime()).toBe(2 * 60 * 60 * 1000);
  });

  it("子块上边缘越出父块 → start 被夹到父 start（时长保留）", () => {
    // 子块 07:00–08:30：越出父块上界，时长 1.5h
    const child = { s: new Date(2026, 8, 15, 7, 0, 0), e: new Date(2026, 8, 15, 8, 30, 0) };
    const r = clampChild(parent.s, parent.e, child.s, child.e);
    expect(r.start.getTime()).toBe(parent.s.getTime()); // 起点夹到 08:00
    expect(r.end.getTime() - r.start.getTime()).toBe(90 * 60 * 1000); // 时长 1.5h 保留
  });

  it("子块完全在父块下方 → 整体平移回父块内（时长保留）", () => {
    const child = { s: new Date(2026, 8, 15, 12, 30, 0), e: new Date(2026, 8, 15, 14, 0, 0) };
    const r = clampChild(parent.s, parent.e, child.s, child.e);
    // 时长 1.5h 保留，整体上移 → 10:30–12:00
    expect(r.end.getTime()).toBe(parent.e.getTime());
    expect(r.end.getTime() - r.start.getTime()).toBe(90 * 60 * 1000);
    expect(r.start.getTime()).toBeGreaterThanOrEqual(parent.s.getTime());
  });

  it("比父还长的子块 → 截断为父跨度", () => {
    const child = { s: TUE_08, e: addDays(TUE_08, 1) }; // 24h > 父 4h
    const r = clampChild(parent.s, parent.e, child.s, child.e);
    expect(r.start.getTime()).toBe(parent.s.getTime());
    expect(r.end.getTime()).toBe(parent.e.getTime());
  });
});
