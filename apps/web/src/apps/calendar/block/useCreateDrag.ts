/**
 * 空白拖拽新建：在网格空白处按下拖动 → 出现虚线预览块 → 松手即创建。
 * 松手时把起点/终点换算成本地时间（吸附 30 分钟），交给上层提交。
 *
 * 预览矩形用 setState 维护（仅一个元素，频率可接受）；若要极致性能可改为
 * 直接操作预览 DOM，但新建交互不触及「一周 50 块拖动」那条性能红线。
 */

import { useCallback, useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";
import { addDays, addMs, startOfDay, snapMinutes, MIN_MS } from "../lib/time";

export interface CreatePreview {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface UseCreateDragOpts {
  hourHeight: number;
  dayWidth: number;
  weekStart: Date;
  /** 返回网格内容区的 client 矩形（用于把指针坐标换算成网格本地坐标）。 */
  getGridRect: () => DOMRect | null;
  onCommit: (startISO: string, endISO: string) => void;
  disabled?: boolean;
}

export function useCreateDrag(opts: UseCreateDragOpts) {
  const { hourHeight, dayWidth, weekStart, getGridRect, onCommit, disabled } = opts;
  const [preview, setPreview] = useState<CreatePreview | null>(null);
  const st = useRef<{ x0: number; y0: number; rect: DOMRect } | null>(null);

  const start = useCallback(
    (e: ReactPointerEvent) => {
      if (disabled || e.button !== 0) return;
      const rect = getGridRect();
      if (!rect) return;
      e.preventDefault();
      e.stopPropagation();
      st.current = { x0: e.clientX, y0: e.clientY, rect };

      const onMove = (ev: PointerEvent) => {
        const r = st.current?.rect;
        if (!r) return;
        const x0l = st.current!.x0 - r.left;
        const y0l = st.current!.y0 - r.top;
        const xl = ev.clientX - r.left;
        const yl = ev.clientY - r.top;
        setPreview({
          x: Math.min(x0l, xl),
          y: Math.min(y0l, yl),
          w: Math.abs(xl - x0l),
          h: Math.abs(yl - y0l),
        });
      };
      const onUp = (ev: PointerEvent) => {
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onUp);
        const r = st.current?.rect;
        setPreview(null);
        if (!r) return;
        const x0l = st.current!.x0 - r.left;
        const y0l = st.current!.y0 - r.top;
        const yl = ev.clientY - r.top;
        const dayIdx = Math.max(0, Math.floor(x0l / dayWidth));
        const aMin = (Math.min(y0l, yl) / hourHeight) * 60;
        const bMin = (Math.max(y0l, yl) / hourHeight) * 60;
        const sMin = snapMinutes(aMin);
        const eMin = Math.max(snapMinutes(bMin), sMin + 30);
        const dayStart = addDays(startOfDay(weekStart), dayIdx);
        const s = addMs(dayStart, sMin * MIN_MS);
        const eEnd = addMs(dayStart, eMin * MIN_MS);
        st.current = null;
        onCommit(s.toISOString(), eEnd.toISOString());
      };
      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp);
    },
    [hourHeight, dayWidth, weekStart, getGridRect, onCommit, disabled],
  );

  return { start, preview };
}
