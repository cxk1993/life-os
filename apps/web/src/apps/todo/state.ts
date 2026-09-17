/**
 * 待办模块本地 UI 状态（只放纯 UI 状态：当前视图、筛选）。
 * 服务端数据一律交给 TanStack Query，不要塞进 store。
 */
import { create } from "zustand";

export type TodoView = "today" | "all" | "recurring";

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
