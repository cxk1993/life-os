import { useCallback } from "react";

import { snap, useDesktopStore } from "./store";
import type { ModuleManifest } from "./types";

export type ResizeDir = "n" | "s" | "e" | "w" | "ne" | "nw" | "se" | "sw";

/**
 * 八向缩放（Pointer Events）。含最小尺寸约束（取 manifest.window.minW/minH）。
 *
 * 与拖动同理：过程只改 `el.style` 的 left/top/width/height，松手才提交 store。
 * 最大化态下 WindowFrame 不会挂载手柄，因此这里无需额外判断。
 *
 * ★ T22：新增 `enabled`。为 false 时**在任何副作用之前返回**
 *   （不 preventDefault/stopPropagation、不 setPointerCapture、不挂监听）——
 *   固定几何的窗口因此完全缩放不了。调用点在固定几何时**干脆不渲染手柄**，这里是第二道保险。
 *
 * ★ 评审修复（2026-09-20）：补 `pointercancel` 分支（与 useDragMove 同款）。
 *   此前缩放中指针被系统取消时，window 上的 pointermove/pointerup 监听泄漏，
 *   且 onMove 不分 pointerId——泄漏期内用户任何鼠标移动都会让窗口跳变变形，
 *   直到下一次 pointerup 才止住并提交错误几何。现以 AbortController 统一收口，
 *   pointercancel 即中止并把样式还原为起始几何（store 未动，无需提交）。
 */
export function useResize(
  instanceId: string,
  elRef: React.RefObject<HTMLElement | null>,
  manifest: ModuleManifest,
  enabled = true,
) {
  return useCallback(
    (e: React.PointerEvent, dir: ResizeDir) => {
      if (!enabled) return; // ★ 先于 e.preventDefault()，不留任何副作用
      const el = elRef.current;
      if (!el) return;
      e.preventDefault();
      e.stopPropagation();
      const id = e.pointerId;
      el.setPointerCapture(id);

      const g0 = currentGeo(instanceId);
      if (!g0) return;
      const sx = e.clientX;
      const sy = e.clientY;
      const minW = manifest.window.minW ?? 360;
      const minH = manifest.window.minH ?? 240;

      const compute = (dx: number, dy: number) => {
        let { x, y, w, h } = g0;
        if (dir.includes("e")) w = Math.max(minW, g0.w + dx);
        if (dir.includes("s")) h = Math.max(minH, g0.h + dy);
        if (dir.includes("w")) {
          w = Math.max(minW, g0.w - dx);
          x = g0.x + (g0.w - w);
        }
        if (dir.includes("n")) {
          h = Math.max(minH, g0.h - dy);
          y = g0.y + (g0.h - h);
        }
        return { x, y, w, h };
      };

      const ac = new AbortController();
      const onMove = (ev: PointerEvent) => {
        const g = compute(ev.clientX - sx, ev.clientY - sy);
        el.style.left = `${g.x}px`;
        el.style.top = `${g.y}px`;
        el.style.width = `${g.w}px`;
        el.style.height = `${g.h}px`;
      };

      const onUp = (ev: PointerEvent) => {
        ac.abort(); // ★ 一次性移除 pointermove/pointerup/pointercancel 全部监听
        el.releasePointerCapture?.(id);
        const g = compute(ev.clientX - sx, ev.clientY - sy);
        useDesktopStore.getState().setGeo(instanceId, {
          x: snap(g.x),
          y: snap(g.y),
          w: snap(g.w),
          h: snap(g.h),
        });
      };

      const onCancel = () => {
        ac.abort();
        el.releasePointerCapture?.(id);
        // ★ store 从未被提交过，把视觉直接还原成起始几何即可
        el.style.left = `${g0.x}px`;
        el.style.top = `${g0.y}px`;
        el.style.width = `${g0.w}px`;
        el.style.height = `${g0.h}px`;
      };

      window.addEventListener("pointermove", onMove, { signal: ac.signal });
      window.addEventListener("pointerup", onUp, { signal: ac.signal });
      window.addEventListener("pointercancel", onCancel, { signal: ac.signal });
    },
    [instanceId, elRef, manifest, enabled],
  );
}

function currentGeo(instanceId: string) {
  return useDesktopStore.getState().windows.find((w) => w.instanceId === instanceId)?.geo ?? null;
}
