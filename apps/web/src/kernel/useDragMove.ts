import { useCallback, useRef } from "react";

import { snap, useDesktopStore } from "./store";

/**
 * 标题栏拖动（Pointer Events）。
 *
 * 性能要点（验收 §6.4）：拖动过程中只改 `el.style.transform`，
 * **不触发 React 重渲染**；松手时才把吸附后的坐标提交给 store。
 * 松手吸附到 8px 网格（SNAP）。
 */
export function useDragMove(instanceId: string, elRef: React.RefObject<HTMLElement | null>) {
  const startX = useRef(0);
  const startY = useRef(0);

  return useCallback(
    (e: React.PointerEvent) => {
      if (e.button !== 0) return;
      const el = elRef.current;
      if (!el) return;
      e.preventDefault();
      const id = e.pointerId;
      el.setPointerCapture(id);
      const baseX = el.offsetLeft;
      const baseY = el.offsetTop;
      startX.current = e.clientX;
      startY.current = e.clientY;

      const onMove = (ev: PointerEvent) => {
        const dx = ev.clientX - startX.current;
        const dy = ev.clientY - startY.current;
        // 直接改样式，避免高频重排/重渲染
        el.style.transform = `translate(${dx}px, ${dy}px)`;
      };

      const onUp = (ev: PointerEvent) => {
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onUp);
        el.releasePointerCapture?.(id);
        el.style.transform = "";
        const dx = ev.clientX - startX.current;
        const dy = ev.clientY - startY.current;
        useDesktopStore.getState().setGeo(instanceId, {
          x: snap(baseX + dx),
          y: snap(baseY + dy),
        });
      };

      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp);
    },
    [instanceId, elRef],
  );
}
