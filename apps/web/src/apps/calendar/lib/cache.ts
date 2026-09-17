/**
 * 事件树在 Query 缓存里的合并原语（纯函数，可单测）。
 * 缓存结构是「根事件数组」，每个根含 children 树。
 */

import type { CalendarEvent } from "../api";

/** 按 id 替换根事件；不存在则追加。用于 SSE created/updated 增量合并。 */
export function replaceRoot(list: CalendarEvent[], next: CalendarEvent): CalendarEvent[] {
  const idx = list.findIndex((e) => e.id === next.id);
  if (idx === -1) return [...list, next];
  const copy = list.slice();
  copy[idx] = next;
  return copy;
}

/** 按 id 删除根事件（连同其子树下整棵移除）。 */
export function removeRoot(list: CalendarEvent[], id: string): CalendarEvent[] {
  return list.filter((e) => e.id !== id);
}
