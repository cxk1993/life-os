/**
 * 本地 UI 状态（纯 UI，不存服务端数据）。
 * 服务端数据一律交给 TanStack Query（见 hooks/useCalendarEvents.ts）。
 */

import { create } from "zustand";

export type ViewMode = "day" | "week" | "month";

export interface ScalePreset {
  label: string;
  hourHeight: number;
}

export const SCALE_PRESETS: ScalePreset[] = [
  { label: "紧凑", hourHeight: 32 },
  { label: "标准", hourHeight: 46 },
  { label: "宽松", hourHeight: 64 },
];

const ZOOM_KEY = "calendar.hourHeight";

function loadHourHeight(): number {
  try {
    const v = localStorage.getItem(ZOOM_KEY);
    if (v) {
      const n = Number(v);
      if (Number.isFinite(n) && n > 0) return n;
    }
  } catch {
    /* ignore */
  }
  return 46;
}

interface CalendarUIState {
  view: ViewMode;
  hourHeight: number;
  selectedId: string | null;
  /** 自动滚到"现在"的触发计数（每次 +1 让网格响应）。 */
  scrollToNowTick: number;
  setView: (v: ViewMode) => void;
  setHourHeight: (h: number) => void;
  select: (id: string | null) => void;
  requestScrollToNow: () => void;
}

export const useCalendarUI = create<CalendarUIState>((set) => ({
  view: "week",
  hourHeight: loadHourHeight(),
  selectedId: null,
  scrollToNowTick: 0,
  setView: (view) => set({ view }),
  setHourHeight: (hourHeight) => {
    try {
      localStorage.setItem(ZOOM_KEY, String(hourHeight));
    } catch {
      /* ignore */
    }
    set({ hourHeight });
  },
  select: (selectedId) => set({ selectedId }),
  requestScrollToNow: () => set((s) => ({ scrollToNowTick: s.scrollToNowTick + 1 })),
}));

/** —— 轻量 toast（乐观更新失败回滚时给主人提示） —— */
export type ToastType = "ok" | "err" | "info";
export interface ToastItem {
  id: number;
  msg: string;
  type: ToastType;
}
interface ToastState {
  toasts: ToastItem[];
  push: (msg: string, type?: ToastType) => void;
  dismiss: (id: number) => void;
}
let toastSeq = 0;
export const useToast = create<ToastState>((set) => ({
  toasts: [],
  push: (msg, type = "info") => {
    const id = ++toastSeq;
    set((s) => ({ toasts: [...s.toasts, { id, msg, type }] }));
    setTimeout(() => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })), 3200);
  },
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));
export const toast = (msg: string, type?: ToastType) => useToast.getState().push(msg, type);
