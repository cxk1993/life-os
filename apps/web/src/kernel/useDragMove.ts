import { useCallback, useRef } from "react";

import { snap, useDesktopStore } from "./store";

/**
 * 标题栏拖动（Pointer Events）。
 *
 * 性能要点（验收 §6.4）：拖动过程中只改 `el.style.transform`，
 * **不触发 React 重渲染**；松手时才把吸附后的坐标提交给 store。
 * 松手吸附到 8px 网格（SNAP）。
 *
 * ★ T22：新增 `enabled`。为 false 时**在任何副作用之前返回**（不 preventDefault、
 *   不 setPointerCapture、不挂 pointermove/pointerup 监听）——
 *   固定几何的窗口因此完全拖不动。调用点同时会把这个 handler 从 `onPointerDown` 上摘掉，
 *   这里是第二道保险。
 *
 * ★ 评审修复（2026-09-20）：补 `pointercancel` 分支。此前拖动中若指针被系统取消
 *   （触屏手势接管 / Alt+Tab / 输入法弹窗等），window 上的 pointermove/pointerup
 *   监听会**泄漏**且 transform 残留；且 onMove 不分 pointerId，泄漏期内用户任何
 *   鼠标移动都会让窗口跟着跳，直到下一次 pointerup 才止住。现以 AbortController
 *   统一管理监听生命周期，pointercancel 即中止并还原视觉位置。
 */
export function useDragMove(
  instanceId: string,
  elRef: React.RefObject<HTMLElement | null>,
  enabled = true,
) {
  const startX = useRef(0);
  const startY = useRef(0);

  return useCallback(
    (e: React.PointerEvent) => {
      if (!enabled) return; // ★ 先于 e.preventDefault()，不留任何副作用
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

      const ac = new AbortController();
      const onMove = (ev: PointerEvent) => {
        const dx = ev.clientX - startX.current;
        const dy = ev.clientY - startY.current;
        // 直接改样式，避免高频重排/重渲染
        el.style.transform = `translate(${dx}px, ${dy}px)`;
      };

      const onUp = (ev: PointerEvent) => {
        ac.abort(); // ★ 一次性移除 pointermove/pointerup/pointercancel 全部监听
        el.releasePointerCapture?.(id);
        el.style.transform = "";
        const dx = ev.clientX - startX.current;
        const dy = ev.clientY - startY.current;
        useDesktopStore.getState().setGeo(instanceId, {
          x: snap(baseX + dx),
          y: snap(baseY + dy),
        });
      };

      const onCancel = () => {
        ac.abort();
        el.releasePointerCapture?.(id);
        el.style.transform = ""; // ★ 拖动从未提交几何，还原视觉即可
      };

      window.addEventListener("pointermove", onMove, { signal: ac.signal });
      window.addEventListener("pointerup", onUp, { signal: ac.signal });
      window.addEventListener("pointercancel", onCancel, { signal: ac.signal });
    },
    [instanceId, elRef, enabled],
  );
}
