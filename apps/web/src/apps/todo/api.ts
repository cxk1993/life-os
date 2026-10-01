/**
 * todo 数据请求层（集中在此，不散落各处）。
 * 跨插件拿数据一律走 HTTP（这里只用 todo 自己的 /api/v1/todo）。
 * 鉴权 / trace_id / RFC7807 解析由 @/shared/api/client 统一处理。
 */
import { api } from "@/shared/api/client";

export type Priority = "high" | "medium" | "low";

export interface TodoItem {
  id: string;
  text: string;
  done: boolean;
  done_at: string | null;
  due_at: string | null;
  priority: Priority | null;
  recur_rule: string | null;
  tags: string[];
  source_path: string | null;
  source_line: number | null;
  sort: number;
  series_id: string | null;
  instance_no: number;
  created_at: string;
  updated_at: string;
}

export interface TodoList {
  items: TodoItem[];
  next_cursor: string | null;
}

/** ★ 2026-09-28：标签汇总的一项（GET /tags；AI 工具 todo_tag_read 同一个端点）。 */
export interface TodoTagCount {
  tag: string;
  todo: number;
  done: number;
  total: number;
}

export interface Summary {
  today: number;
  overdue: number;
  week_done: number;
}

/** U2 today-summary 规范 v1（workbuddy 定稿）：{title, items≤5:[{text,state,count}], link}。 */
export interface TodaySummary {
  title?: string;
  items: Array<{ text: string; state?: "info" | "due" | "done" | "alert"; count?: number }>;
  link?: string;
  /** todo 扩展：今日已完成数（视图可选展示）。 */
  done?: number;
}

export interface ImportResult {
  imported: number;
  lines: number;
  items: TodoItem[];
}

export interface ExportResult {
  markdown: string;
}

/**
 * 待办状态筛选（与后端 `GET /items?status=` 对齐）。
 *
 * ★ 2026-10-02（主人令「已完成满 7 天自动归档」）：
 *   新增 `active` / `archived`。归档是 **done_at 老化** 的函数 ——
 *   `done` = 打勾在归档期内，`archived` = 打勾已过归档期，两者**互斥**；
 *   `active` 是 `archived` 的补集（未完成 + 打勾未满期）。
 *   `all` 仍返回一切（含归档）。
 */
export type TodoStatus = "done" | "todo" | "all" | "active" | "archived";

export interface ListParams {
  status?: TodoStatus;
  due_before?: string;
  due_after?: string;
  tag?: string;
  source?: string;
  limit?: number;
  cursor?: string | null;
}

const BASE = "/api/v1/todo";

export const todoApi = {
  list: (params: ListParams = {}) => {
    const q = new URLSearchParams();
    if (params.status && params.status !== "all") q.set("status", params.status);
    if (params.due_before) q.set("due_before", params.due_before);
    if (params.due_after) q.set("due_after", params.due_after);
    if (params.tag) q.set("tag", params.tag);
    if (params.source) q.set("source", params.source);
    if (params.limit) q.set("limit", String(params.limit));
    if (params.cursor) q.set("cursor", params.cursor);
    const qs = q.toString();
    return api.get<TodoList>(`${BASE}/items${qs ? `?${qs}` : ""}`);
  },

  // raw：一行 Obsidian 语法（含 @日期/!优先级/#标签 语法糖），服务端解析
  create: (raw: string) => api.post<TodoItem>(`${BASE}/items`, { raw }),

  // ★ 归一化（总监令2 防御补丁）：后端 TodoCreate 只认 raw|text，不认 title。
  // 历史调用方若误传 title 或空 text → pydantic 忽略 extra → 422 "text 不能为空"。
  // 请求出口做一次清洗：title→text、空 text 回退 raw、剥离只读字段（id/done/...）。
  createStructured: (
    body: Partial<TodoItem> & { due_at?: string | null; title?: string; raw?: string },
  ) => {
    const { title, text, due_at, priority, recur_rule, tags, raw } = body;
    const normalized: Record<string, unknown> = {};
    const finalText = (text ?? title ?? "").trim();
    if (finalText) normalized.text = finalText;
    else if (raw) normalized.raw = raw;
    else normalized.raw = String(title ?? text ?? "");
    if (due_at) normalized.due_at = due_at;
    if (priority) normalized.priority = priority;
    if (recur_rule) normalized.recur_rule = recur_rule;
    if (tags?.length) normalized.tags = tags;
    return api.post<TodoItem>(`${BASE}/items`, normalized);
  },

  update: (id: string, body: Partial<TodoItem>) => api.patch<TodoItem>(`${BASE}/items/${id}`, body),

  remove: (id: string) => api.delete<void>(`${BASE}/items/${id}`),

  toggle: (id: string) => api.post<TodoItem>(`${BASE}/items/${id}/toggle`),

  importMarkdown: (content: string) => api.post<ImportResult>(`${BASE}/import`, { content }),

  exportMarkdown: (status?: "done" | "todo" | "all") =>
    api.post<ExportResult>(`${BASE}/export`, { status: status ?? "all" }),

  summary: () => api.get<Summary>(`${BASE}/summary`),

  /** ★ 2026-09-28：标签汇总 —— 动态标签条的数据源（一份数据同时喂 AI 与前端）。 */
  tags: () => api.get<TodoTagCount[]>(`${BASE}/tags`),

  /** U2 today-summary（派工令 62 · todo 源）。 */
  todaySummary: () => api.get<TodaySummary>(`${BASE}/today-summary`),
};
