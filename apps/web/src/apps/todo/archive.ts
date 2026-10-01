/**
 * 归档判据的前端镜像（★ 2026-10-02 · 主人令）。
 *
 * ── 为什么前端也要有一份 ──────────────────────────────────────────
 * 后端按 `status=archived` 筛（真判据在 SQL 里）。但**学业页**取的是
 * `status=all`（它要自己分「最急 / 未排期 / 已完成」三组），拿到的是全量数据，
 * 于是它必须在本地把归档项摘出去 —— 否则「展开已完成」里还会躺着几十天前
 * 打完的旧作业，正是主人要消除的那个观感。
 *
 * ⚠️ 两份实现必须**同一条规则**。这边改了口径、那边没改，就会出现
 * 「已完成里没了、归档里也没有」的凭空消失。后端有
 * `test_archive_threshold_is_seven_days` 钉住阈值，前端有
 * `archive.test.ts` 钉住行为 —— 任一侧漂移都会红。
 */
import type { TodoItem } from "./api";
import { ARCHIVE_AFTER_DAYS } from "./constants";

const MS_PER_DAY = 86_400_000;

/**
 * 该条是否已归档：已完成 **且** 打勾满 ARCHIVE_AFTER_DAYS 天。
 *
 * @param item 待办
 * @param now  当前时刻（可注入，便于测试与「同一次渲染内口径一致」）
 *
 * ⚠️ `done` 为真但 `done_at` 为空（历史脏数据）**不算归档** ——
 *    判不了龄就不归档，宁可多显示一条，也不能让它悄悄消失。与后端一致。
 */
export function isArchived(item: TodoItem, now: Date = new Date()): boolean {
  if (!item.done || !item.done_at) return false;
  const t = new Date(item.done_at).getTime();
  if (Number.isNaN(t)) return false;
  return t < now.getTime() - ARCHIVE_AFTER_DAYS * MS_PER_DAY;
}
