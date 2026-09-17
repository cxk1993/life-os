/**
 * 块拖动：纵向吸附 30 分钟、横向吸附 1 天。
 *
 * 性能纪律（验收 #1 / 模板包 §6）：拖动过程**直接改 el.style.transform**，
 * 用 requestAnimationFrame 节流，**不每帧 setState**；松手才计算吸附后的
 * 整数 delta（dDays / dHours）交给上层提交。
 */

import { useCallback, useRef } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";
import { SNAP_MIN } from "../lib/time";

export interface DragDelta {
  dDays: number;
  dHours: number;
}

export interface UseBlockDragOpts {
  hourHeight: number;
  dayWidth: number;
  onCommit: (d: DragDelta) => void;
  disabled?: boolean;
}

export function useBlockDrag(opts: UseBlockDragOpts) {
  const { hourHeight, dayWidth, onCommit, disabled } = opts;
  const st = useRef<{
    el: HTMLElement | null;
    x0: number;
    y0: number;
    raf: number;
  } | null>(null);

  const start = useCallback(
    (e: ReactPointerEvent) => {
      if (disabled || e.button !== 0) return;
      const el = e.currentTarget as HTMLElement;
      e.preventDefault();
      e.stopPropagation();
      if (e.pointerId !== undefined) el.setPointerCapture?.(e.pointerId);
      el.classList.add("dragging");
      st.current = { el, x0: e.clientX, y0: e.clientY, raf: 0 };

      const onMove = (ev: PointerEvent) => {
        const s = st.current;
        if (!s) return;
        const dx = ev.clientX - s.x0;
        const dy = ev.clientY - s.y0;
        if (s.raf) cancelAnimationFrame(s.raf);
        s.raf = requestAnimationFrame(() => {
          if (s.el) s.el.style.transform = `translate(${dx}px, ${dy}px)`;
        });
      };
      const onUp = (ev: PointerEvent) => {
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onUp);
        const s = st.current;
        if (!s) return;
        if (s.raf) cancelAnimationFrame(s.raf);
        s.el?.classList.remove("dragging");
        if (s.el) s.el.style.transform = "";
        if (ev.pointerId !== undefined) s.el?.releasePointerCapture?.(ev.pointerId);
        const dx = ev.clientX - s.x0;
        const dy = ev.clientY - s.y0;
        const dHours = Math.round(dy / hourHeight / (SNAP_MIN / 60)) * (SNAP_MIN / 60);
        const dDays = Math.round(dx / dayWidth);
        st.current = null;
        onCommit({ dDays, dHours });
      };
      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp);
    },
    [hourHeight, dayWidth, onCommit, disabled],
  );

  return { start };
}
