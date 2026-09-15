import { useCallback } from "react";

import { snap, useDesktopStore } from "./store";
import type { ModuleManifest } from "./types";

export type ResizeDir = "n" | "s" | "e" | "w" | "ne" | "nw" | "se" | "sw";

/**
 * 八向缩放（Pointer Events）。含最小尺寸约束（取 manifest.window.minW/minH）。
 *
 * 与拖动同理：过程只改 `el.style` 的 left/top/width/height，松手才提交 store。
 * 最大化态下 WindowFrame 不会挂载手柄，因此这里无需额外判断。
 */
export function useResize(
  instanceId: string,
  elRef: React.RefObject<HTMLElement | null>,
  manifest: ModuleManifest,
) {
  return useCallback(
    (e: React.PointerEvent, dir: ResizeDir) => {
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

      const onMove = (ev: PointerEvent) => {
        const g = compute(ev.clientX - sx, ev.clientY - sy);
        el.style.left = `${g.x}px`;
        el.style.top = `${g.y}px`;
        el.style.width = `${g.w}px`;
        el.style.height = `${g.h}px`;
      };

      const onUp = (ev: PointerEvent) => {
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onUp);
        el.releasePointerCapture?.(id);
        const g = compute(ev.clientX - sx, ev.clientY - sy);
        useDesktopStore.getState().setGeo(instanceId, {
          x: snap(g.x),
          y: snap(g.y),
          w: snap(g.w),
          h: snap(g.h),
        });
      };

      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp);
    },
    [instanceId, elRef, manifest],
  );
}

function currentGeo(instanceId: string) {
  return useDesktopStore.getState().windows.find((w) => w.instanceId === instanceId)?.geo ?? null;
}
