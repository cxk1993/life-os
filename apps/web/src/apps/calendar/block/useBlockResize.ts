/**
 * 块缩放：下缘改时长（最短 30 分钟）、右缘改跨天（span_days）。
 *
 * 与 useBlockDrag 同样的「transform 直接改样式 + rAF 节流」纪律；
 * 松手把吸附后的整数 delta 交给上层，钳制（最短 30 分钟 / 不越过当日 24:00 /
 * 不越周界）由 lib/time.ts 的 applyResizeBottom / applyResizeRight 完成。
 */

import { useCallback, useRef } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";
import { SNAP_MIN } from "../lib/time";

export type ResizeMode = "bottom" | "right";

export interface ResizeDelta {
  dHours: number; // 下缘用：改变 end（以小时计，吸附 0.5h）
  dDays: number; // 右缘用：改变 end（以天计，吸附 1 天）
}

export interface UseBlockResizeOpts {
  hourHeight: number;
  dayWidth: number;
  onCommit: (mode: ResizeMode, d: ResizeDelta) => void;
  disabled?: boolean;
}

export function useBlockResize(opts: UseBlockResizeOpts) {
  const { hourHeight, dayWidth, onCommit, disabled } = opts;
  const st = useRef<{
    el: HTMLElement | null;
    x0: number;
    y0: number;
    raf: number;
  } | null>(null);

  const start = useCallback(
    (mode: ResizeMode) => (e: ReactPointerEvent) => {
      if (disabled || e.button !== 0) return;
      const el = e.currentTarget as HTMLElement;
      e.preventDefault();
      e.stopPropagation();
      if (e.pointerId !== undefined) el.setPointerCapture?.(e.pointerId);
      el.classList.add("resizing");
      st.current = { el, x0: e.clientX, y0: e.clientY, raf: 0 };

      const onMove = (ev: PointerEvent) => {
        const s = st.current;
        if (!s) return;
        const dx = ev.clientX - s.x0;
        const dy = ev.clientY - s.y0;
        if (s.raf) cancelAnimationFrame(s.raf);
        s.raf = requestAnimationFrame(() => {
          if (!s.el) return;
          if (mode === "bottom") {
            s.el.style.height = `${s.el.offsetHeight + dy}px`;
          } else {
            s.el.style.width = `${s.el.offsetWidth + dx}px`;
          }
        });
      };
      const onUp = (ev: PointerEvent) => {
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onUp);
        const s = st.current;
        if (!s) return;
        if (s.raf) cancelAnimationFrame(s.raf);
        s.el?.classList.remove("resizing");
        if (s.el) {
          s.el.style.height = "";
          s.el.style.width = "";
        }
        if (ev.pointerId !== undefined) s.el?.releasePointerCapture?.(ev.pointerId);
        const dx = ev.clientX - s.x0;
        const dy = ev.clientY - s.y0;
        const dHours = Math.round(dy / hourHeight / (SNAP_MIN / 60)) * (SNAP_MIN / 60);
        const dDays = Math.round(dx / dayWidth);
        st.current = null;
        onCommit(mode, { dHours, dDays });
      };
      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp);
    },
    [hourHeight, dayWidth, onCommit, disabled],
  );

  return { start };
}
