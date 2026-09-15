import { create } from "zustand";

export type ToastKind = "info" | "ok" | "warn" | "danger";

interface ToastItem {
  id: number;
  kind: ToastKind;
  msg: string;
}

interface ToastState {
  items: ToastItem[];
  push: (kind: ToastKind, msg: string) => void;
  remove: (id: number) => void;
}

const useToastStore = create<ToastState>((set) => ({
  items: [],
  push: (kind, msg) => {
    const id = Date.now() + Math.random();
    set((s) => ({ items: [...s.items, { id, kind, msg }] }));
    setTimeout(() => {
      set((s) => ({ items: s.items.filter((t) => t.id !== id) }));
    }, 3200);
  },
  remove: (id) => set((s) => ({ items: s.items.filter((t) => t.id !== id) })),
}));

/** 命令式弹 toast：toast('ok', '已保存')。 */
export function toast(kind: ToastKind, msg: string): void {
  useToastStore.getState().push(kind, msg);
}

/** 在组件里拿 push 方法。 */
export function useToast(): (kind: ToastKind, msg: string) => void {
  return useToastStore((s) => s.push);
}

/** 渲染层，挂在桌面根部。 */
export function ToastHost() {
  const items = useToastStore((s) => s.items);
  return (
    <div className="toast-stack" aria-live="polite">
      {items.map((t) => (
        <div key={t.id} className={`toast toast--${t.kind}`} role="status">
          {t.msg}
        </div>
      ))}
    </div>
  );
}
