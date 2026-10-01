/**
 * 待办模块本地 UI 状态（只放纯 UI 状态：当前视图、筛选）。
 * 服务端数据一律交给 TanStack Query，不要塞进 store。
 */
import { create } from "zustand";

/**
 * ★ 2026-10-02（主人令）：新增 `archived` —— 已完成满 7 天自动归档的「第三栏」。
 * 归档不是一种状态字段，是 done_at 老化的函数（后端按 `status=archived` 筛），
 * 所以这里只是一个视图，没有任何「归档」动作要调。
 */
export type TodoView = "today" | "all" | "recurring" | "archived";

interface TodoUIState {
  view: TodoView;
  /** 仅显示指定标签（null = 不过滤） */
  filterTag: string | null;
  setView: (v: TodoView) => void;
  setFilterTag: (t: string | null) => void;
}

export const useTodoUI = create<TodoUIState>((set) => ({
  view: "today",
  filterTag: null,
  setView: (view) => set({ view }),
  setFilterTag: (filterTag) => set({ filterTag }),
}));
