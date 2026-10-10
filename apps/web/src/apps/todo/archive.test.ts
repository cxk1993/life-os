/**
 * 归档判据测试（★ 2026-10-02 · 主人「已完成满 7 天自动归档」）。
 *
 * ── 为什么要单独测这个纯函数 ──────────────────────────────────────
 * 后端按 `status=archived` 筛，但**学业页**取的是 `status=all`（它要自己
 * 分三组），必须在前端本地把归档项摘出去 —— 于是同一套规则存在两份实现：
 * 一份是后端的 SQL，一份是这个函数。**两份漂移 = 有东西会凭空消失**，
 * 所以这里把前端这一份钉死。
 *
 * ⚠️ 不要用「相对今天的天数」写断言（`setDate(getDate() - n)`）——
 *    那是坑谱 #49 的「周一才红」型 flake。这里一律注入固定的 now。
 */
import { describe, it, expect } from "vitest";

import { isArchived, daysUntilArchive } from "./archive";
import { ARCHIVE_AFTER_DAYS } from "./constants";
import type { TodoItem } from "./api";

const NOW = new Date("2026-10-02T12:00:00+08:00");

function mk(over: Partial<TodoItem> = {}): TodoItem {
  return {
    id: "x",
    text: "样本",
    done: false,
    done_at: null,
    due_at: null,
    priority: null,
    recur_rule: null,
    tags: [],
    source_path: null,
    source_line: null,
    sort: 0,
    series_id: "x",
    instance_no: 0,
    created_at: "2026-09-01T00:00:00+08:00",
    updated_at: "2026-09-01T00:00:00+08:00",
    ...over,
  };
}

/** 距 NOW 若干天前完成的条目。 */
function doneDaysAgo(days: number): TodoItem {
  return mk({
    done: true,
    done_at: new Date(NOW.getTime() - days * 86_400_000).toISOString(),
  });
}

describe("isArchived（归档判据）", () => {
  it("阈值就是 7 天（与后端 ARCHIVE_AFTER_DAYS 同源）", () => {
    expect(ARCHIVE_AFTER_DAYS).toBe(7);
  });

  it("未完成的永远不归档（哪怕很久没动）", () => {
    expect(isArchived(mk({ done: false, due_at: "2026-01-01T00:00:00+08:00" }), NOW)).toBe(false);
  });

  it("刚打勾的不归档", () => {
    expect(isArchived(doneDaysAgo(0), NOW)).toBe(false);
  });

  it("6.5 天前打勾：还没到 7 天 → 不归档", () => {
    expect(isArchived(doneDaysAgo(6.5), NOW)).toBe(false);
  });

  it("7.5 天前打勾：已过 7 天 → 归档", () => {
    expect(isArchived(doneDaysAgo(7.5), NOW)).toBe(true);
  });

  it("打勾很久的（30 天）→ 归档", () => {
    expect(isArchived(doneDaysAgo(30), NOW)).toBe(true);
  });

  it("★ 脏数据：done 为真但 done_at 为空 → 不归档（宁可多显示，不可凭空消失）", () => {
    expect(isArchived(mk({ done: true, done_at: null }), NOW)).toBe(false);
  });

  it("★ 脏数据：done_at 不是合法时间 → 不归档", () => {
    expect(isArchived(mk({ done: true, done_at: "not-a-date" }), NOW)).toBe(false);
  });

  it("★ 防回退：判据必须**依赖 now 参数**，不能用 Date.now() 硬取当前时刻", () => {
    // 同一条数据，两个不同的「现在」应当得出相反结论 ——
    // 若实现里写死了 new Date()，这条立刻红。
    const item = doneDaysAgo(5);
    const later = new Date(NOW.getTime() + 3 * 86_400_000); // 再过 3 天 → 满 8 天
    expect(isArchived(item, NOW)).toBe(false);
    expect(isArchived(item, later)).toBe(true);
  });
});

describe("daysUntilArchive（归档倒计时）", () => {
  // ★ 2026-10-02（主人「打钩日期要能看见」）：主人看不到打钩日期就无从验证
  //   「满 7 天归档」这条规则 —— 倒计时把它变成看得见的东西。
  it("刚打勾 → 还剩 7 天", () => {
    expect(daysUntilArchive(doneDaysAgo(0), NOW)).toBe(7);
  });

  it("1 天前打勾 → 还剩 6 天", () => {
    expect(daysUntilArchive(doneDaysAgo(1), NOW)).toBe(6);
  });

  it("6.5 天前打勾 → 还剩 1 天（向上取整，不显示 0）", () => {
    // 0.5 天剩量必须显示「1 天后」—— 显示「0 天后」像是已经归档了，会误导。
    expect(daysUntilArchive(doneDaysAgo(6.5), NOW)).toBe(1);
  });

  it("已归档（7.5 天前打勾）→ null（不在归档栏再报倒计时）", () => {
    expect(daysUntilArchive(doneDaysAgo(7.5), NOW)).toBeNull();
  });

  it("未完成 → null（没打钩谈不上归档）", () => {
    expect(daysUntilArchive(mk({ done: false }), NOW)).toBeNull();
  });

  it("★ 脏数据 done_at 为空 / 非法 → null", () => {
    expect(daysUntilArchive(mk({ done: true, done_at: null }), NOW)).toBeNull();
    expect(daysUntilArchive(mk({ done: true, done_at: "garbage" }), NOW)).toBeNull();
  });

  it("★ 与 isArchived 互补且不重叠：有倒计时的必未归档，已归档的必无倒计时", () => {
    for (const d of [0, 1, 3, 6.5, 6.9, 7.1, 7.5, 30]) {
      const it = doneDaysAgo(d);
      const archived = isArchived(it, NOW);
      const left = daysUntilArchive(it, NOW);
      expect(archived).toBe(left === null); // 恰好一个成立
    }
  });
});
