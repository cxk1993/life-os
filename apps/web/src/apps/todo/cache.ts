/**
 * todo 域缓存的**安全**写入助手（★ 2026-09-28 · 云昔）。
 *
 * ── 为什么有它（真实事故，主人报的"点勾没反应"）────────────────────
 * `["todo"]` 这层命名空间下住着**好几种形状完全不同**的缓存：
 *
 *   · 列表：`{ items: TodoItem[], next_cursor }`   ← all / today / recurring / study
 *   · 标签：`TodoTag[]`（**是数组！**）
 *   · 概览：`{ today, overdue, week_done }`、`{ title, items, count }`（**没有 items**）
 *
 * 而 `ItemRow` 的乐观更新曾经直接写 `old.items.map(...)` ⇒ 一旦撞上后两种，
 * 当场抛 `TypeError: Cannot read properties of undefined (reading 'map')` ✗
 *
 * 后果极隐蔽（值得记下来）：
 *   `onMutate` **先于** `mutationFn` 执行 ⇒ 它在抛错的那一刻就把整个 mutation 打断了
 *   ⇒ **`mutationFn` 根本没机会发请求** ⇒ 服务端日志里**只有 GET（onSettled 的刷新）、
 *   没有 POST** ⇒ 数据没变、界面不动 ⇒ 主人看到的正是"点勾没反应" ✗
 *
 * 所以规矩是：**凡往 todo 域缓存里写，都必须先确认它真是列表缓存。**
 * 形状不符就**原样返回**（宁可少更新一个缓存，也不能把整个操作炸掉）。
 */
import type { QueryClient } from "@tanstack/react-query";

import type { TodoItem } from "./api";
import { TODO_KEY_ROOT } from "./keys";

interface ListCache {
  items: TodoItem[];
}

/**
 * 只对**真正的列表缓存**施加 updater；形状不符的原样返回，**绝不抛错**。
 *
 * @param qc      QueryClient
 * @param updater 接收该缓存的 items 数组，返回新的 items 数组
 * @param also    额外的 key 前缀过滤（默认只匹配 TODO_KEY_ROOT 之下）
 */
export function updateTodoListCaches(
  qc: QueryClient,
  updater: (items: TodoItem[]) => TodoItem[],
): void {
  qc.setQueriesData<unknown>({ queryKey: [TODO_KEY_ROOT] }, (old: unknown) => {
    if (!old || typeof old !== "object" || Array.isArray(old)) return old; // 标签是数组 → 跳过
    const items = (old as ListCache).items;
    if (!Array.isArray(items)) return old; // 概览类没有 items → 跳过
    return { ...(old as object), items: updater(items) };
  });
}

/** 判断一个缓存值是不是列表缓存（给测试与别处复用）。 */
export function isTodoListCache(value: unknown): value is ListCache {
  return !!value && typeof value === "object" && !Array.isArray(value)
    && Array.isArray((value as ListCache).items);
}
