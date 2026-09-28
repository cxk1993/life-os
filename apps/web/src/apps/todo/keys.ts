/**
 * todo 域的 React Query key 命名空间（★ 2026-09-28 · 云昔）。
 *
 * ── 为什么需要这个文件（真实事故，不是假想）───────────────────────────
 * `ItemRow` 是**共用组件**：「待办」页与「学业」页都渲染它。它的乐观更新与
 * 失效刷新只作用于 `["todo"]` 前缀的缓存。
 *
 * 而学业页当初把 key 写成了 `["study", "list"]` ⇒ 于是**在学业页点勾**：
 *   ① 请求成功（服务端日志 200，数据真的改了）
 *   ② 乐观更新写进 `["todo"]` 缓存 —— 学业页读的是 `["study","list"]`，**纹丝不动** ✗
 *   ③ 失效刷新也只刷 `["todo"]` —— 学业页**永远不会重新取数** ✗
 *   ⇒ **画面毫无变化**。主人以为没生效，又点一次 ⇒ **两次互相抵消，作业白勾了** ✗✗
 *
 * ── 治本 ────────────────────────────────────────────────────────
 * **key 的前缀只能有一个来源。** 任何渲染 todo 数据的视图，都必须把自己的 key
 * 挂在 `TODO_KEY_ROOT` 之下 —— 这样共用的 `ItemRow`、以及插件事件
 * （`todo.item.updated` 的自动刷新）才能覆盖到它。
 *
 * ⚠️ 新增视图时请写 `[TODO_KEY_ROOT, "<你的域>", ...]`，**不要另起一个根**。
 */
export const TODO_KEY_ROOT = "todo" as const;

/** 造一个挂在 todo 域下的 key：`todoKey("study", "list")` → `["todo","study","list"]` */
export function todoKey(...parts: (string | undefined)[]): unknown[] {
  return [TODO_KEY_ROOT, ...parts];
}
