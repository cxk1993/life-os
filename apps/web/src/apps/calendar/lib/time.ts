/**
 * 日程表纯逻辑层（无 React 依赖，可单测）。
 *
 * 所有时间运算都在「浏览器本地时区」进行：后端返回带时区的 ISO，
 * 用 new Date() 解析后即本地墙钟时间，与主人所在时区一致。
 *
 * 本文件的函数全部是纯函数，吸附 / 钳制 / 跨天拆分 / 重叠检测 / 子块不越父
 * 等都集中在这里，方便用 jsdom + 合成事件做确定性测试（见 time.test.ts）。
 */

export const MIN_MS = 60_000;
export const HOUR_MS = 3_600_000;
export const DAY_MS = 86_400_000;

/**
 * 主人固定时区：东八区（Asia/Shanghai）。
 * 日历拉取窗口的 `from`/`to` 必须带 `+08:00`，否则后端 to_utc 按 UTC 截断，
 * 早 8 点的事件会被漏掉（实测踩过）。这里集中提供"东八区墙钟 ⇄ UTC instant"换算。
 */
export const SH_UTC_OFFSET_MS = 8 * HOUR_MS;

/** 把"东八区墙钟"转成 UTC 的 Date（month 为 1-12，便于时间运算 / 与后端对齐）。 */
export function shWallClock(y: number, mo: number, d: number, h = 0, mi = 0, s = 0, ms = 0): Date {
  // 东八区墙钟比 UTC 早 8 小时：SH 2026-09-14 00:00 = UTC 2026-09-13 16:00。
  return new Date(Date.UTC(y, mo - 1, d, h, mi, s, ms) - SH_UTC_OFFSET_MS);
}

/** 给定任意 UTC instant，返回它在东八区的墙钟年月日星期（仅用于取分量）。 */
export function shWallParts(utc: Date): { y: number; mo: number; d: number; wd: number } {
  const sh = new Date(utc.getTime() + SH_UTC_OFFSET_MS);
  return {
    y: sh.getUTCFullYear(),
    mo: sh.getUTCMonth() + 1,
    d: sh.getUTCDate(),
    wd: sh.getUTCDay(),
  };
}

/** 把任意 UTC instant 格式化为东八区 ISO 字符串（带 +08:00），后端 to_utc 据此解析。 */
export function formatSH(utc: Date): string {
  const sh = new Date(utc.getTime() + SH_UTC_OFFSET_MS);
  const p2 = (n: number) => String(n).padStart(2, "0");
  const p3 = (n: number) => String(n).padStart(3, "0");
  return (
    `${sh.getUTCFullYear()}-${p2(sh.getUTCMonth() + 1)}-${p2(sh.getUTCDate())}` +
    `T${p2(sh.getUTCHours())}:${p2(sh.getUTCMinutes())}:${p2(sh.getUTCSeconds())}.${p3(sh.getUTCMilliseconds())}+08:00`
  );
}

/** 计算东八区"本周一 00:00"对应的 UTC instant（周一=0）。 */
export function shMonday(utc: Date): Date {
  const { y, mo, d, wd } = shWallParts(utc);
  return shWallClock(y, mo, d - ((wd + 6) % 7), 0, 0, 0, 0);
}

/** 纵向吸附粒度：30 分钟。 */
export const SNAP_MIN = 30;

export function startOfDay(d: Date): Date {
  const n = new Date(d);
  n.setHours(0, 0, 0, 0);
  return n;
}

export function addDays(d: Date, n: number): Date {
  const x = new Date(d);
  x.setDate(x.getDate() + n);
  return x;
}

export function addMs(d: Date, ms: number): Date {
  return new Date(d.getTime() + ms);
}

/** 把一个分钟数吸附到最近的 SNAP_MIN 倍数。 */
export function snapMinutes(totalMin: number): number {
  return Math.round(totalMin / SNAP_MIN) * SNAP_MIN;
}

/** 把任意时刻吸附到当天 30 分钟网格。 */
export function snapToGrid(date: Date, dayStart: Date): Date {
  const offMin = (date.getTime() - dayStart.getTime()) / MIN_MS;
  return addMs(dayStart, snapMinutes(offMin) * MIN_MS);
}

/** 事件跨越的自然天数（周五 20:00 → 周六 02:00 计 2 天）。 */
export function spanDaysOf(start: Date, end: Date): number {
  const diff = startOfDay(end).getTime() - startOfDay(start).getTime();
  return Math.max(1, Math.round(diff / DAY_MS) + 1);
}

/** 某日期在「周起始日」坐标系下的列索引（0=周一…6=周日）。 */
export function dayIndexInWeek(date: Date, weekStart: Date): number {
  const diff = startOfDay(date).getTime() - startOfDay(weekStart).getTime();
  return Math.round(diff / DAY_MS);
}

export interface Segment {
  dayIndex: number;
  start: Date;
  end: Date;
  isFirst: boolean;
  isLast: boolean;
}

/**
 * 把 [start,end) 拆成「每天一段」的连续片段，用于跨天块在每列连续渲染。
 * weekStart 仅用于计算 dayIndex（列号）。
 */
export function segmentEvent(start: Date, end: Date, weekStart: Date): Segment[] {
  const segs: Segment[] = [];
  const weekStart0 = startOfDay(weekStart);
  let cur = startOfDay(start);
  const lastDay = startOfDay(end);
  let first = true;
  while (cur <= lastDay) {
    const dayEnd = addDays(cur, 1);
    const segStart = cur <= start ? start : cur;
    const segEnd = dayEnd <= end ? dayEnd : end;
    if (segEnd.getTime() > segStart.getTime()) {
      segs.push({
        dayIndex: Math.round((cur.getTime() - weekStart0.getTime()) / DAY_MS),
        start: segStart,
        end: segEnd,
        isFirst: first,
        isLast: segEnd >= end,
      });
    }
    first = false;
    cur = dayEnd;
  }
  return segs;
}

export function overlaps(aS: Date, aE: Date, bS: Date, bE: Date): boolean {
  return aS.getTime() < bE.getTime() && bS.getTime() < aE.getTime();
}

/**
 * 同一列内是否存在时间重叠（用于「编辑冲突」温和提示）。
 * 输入是该列所有片段的 [start,end)。
 */
export function hasOverlapInColumn(segments: Array<{ start: Date; end: Date }>): boolean {
  const sorted = [...segments].sort((a, b) => a.start.getTime() - b.start.getTime());
  for (let i = 1; i < sorted.length; i++) {
    if (overlaps(sorted[i - 1].start, sorted[i - 1].end, sorted[i].start, sorted[i].end)) {
      return true;
    }
  }
  return false;
}

export interface WeekBounds {
  weekStart: Date;
  weekDays: number;
}

/**
 * 拖动整块：纵向吸附 30min、横向吸附整天数，并钳制在 [周起始, 周起始+weekDays] 内。
 * dHours/dDays 已由调用方吸附好；这里只做钳制。
 */
export function applyMove(
  start: Date,
  end: Date,
  dDays: number,
  dHours: number,
  bounds: WeekBounds,
): { start: Date; end: Date; spanDays: number } {
  const deltaMs = dDays * DAY_MS + dHours * HOUR_MS;
  let ns = addMs(start, deltaMs);
  let ne = addMs(end, deltaMs);
  const weekStart0 = startOfDay(bounds.weekStart);
  const weekEnd = addDays(weekStart0, bounds.weekDays);
  if (ns.getTime() < weekStart0.getTime()) {
    const dd = weekStart0.getTime() - ns.getTime();
    ns = addMs(ns, dd);
    ne = addMs(ne, dd);
  }
  if (ne.getTime() > weekEnd.getTime()) {
    const dd = ne.getTime() - weekEnd.getTime();
    ns = addMs(ns, -dd);
    ne = addMs(ne, -dd);
  }
  return { start: ns, end: ne, spanDays: spanDaysOf(ns, ne) };
}

/**
 * 下缘拉伸改时长：改变 end，最短 30 分钟，且不得跨过当天 24:00（跨天用右缘）。
 */
export function applyResizeBottom(
  start: Date,
  end: Date,
  dHours: number,
  minMin = 30,
): { start: Date; end: Date } {
  let ne = addMs(end, dHours * HOUR_MS);
  const dayEnd = addDays(startOfDay(start), 1);
  if (ne.getTime() > dayEnd.getTime()) ne = dayEnd;
  const minMs = minMin * MIN_MS;
  if (ne.getTime() - start.getTime() < minMs) ne = addMs(start, minMs);
  return { start, end: ne };
}

/**
 * 右缘拉伸改跨天：改变 end，按整天数延展，更新 spanDays；最短 30 分钟、钳制在周内。
 */
export function applyResizeRight(
  start: Date,
  end: Date,
  dDays: number,
  bounds: WeekBounds,
  minMin = 30,
): { start: Date; end: Date; spanDays: number } {
  let ne = addMs(end, dDays * DAY_MS);
  const weekEnd = addDays(startOfDay(bounds.weekStart), bounds.weekDays);
  if (ne.getTime() > weekEnd.getTime()) ne = weekEnd;
  const minMs = minMin * MIN_MS;
  if (ne.getTime() - start.getTime() < minMs) ne = addMs(start, minMs);
  return { start, end: ne, spanDays: spanDaysOf(start, ne) };
}

/**
 * 子块钳制进父块边界（保留时长，装不下则取父块跨度）。
 * 用于：新建子块、移动/缩放子块时，保证子块不越父块。
 */
export function clampChild(
  pStart: Date,
  pEnd: Date,
  cStart: Date,
  cEnd: Date,
): { start: Date; end: Date } {
  const dur = cEnd.getTime() - cStart.getTime();
  if (dur >= pEnd.getTime() - pStart.getTime()) {
    return { start: pStart, end: pEnd };
  }
  let ns = cStart.getTime();
  if (ns < pStart.getTime()) ns = pStart.getTime();
  if (ns + dur > pEnd.getTime()) ns = pEnd.getTime() - dur;
  return { start: new Date(ns), end: new Date(ns + dur) };
}

/** 把整棵事件树按 delta 平移（父块移动/缩放时子块跟随）。 */
export function shiftTree<T extends { start_at: string; end_at: string; children?: T[] }>(
  ev: T,
  deltaMs: number,
): T {
  const shifted: T = {
    ...ev,
    start_at: addMs(new Date(ev.start_at), deltaMs).toISOString(),
    end_at: addMs(new Date(ev.end_at), deltaMs).toISOString(),
  };
  if (ev.children && ev.children.length) {
    (shifted as { children?: T[] }).children = ev.children.map((c) => shiftTree(c, deltaMs));
  }
  return shifted;
}
