import { Component, lazy, Suspense, useMemo, useRef } from "react";
import type { ReactNode } from "react";

import { Skeleton } from "@/shared/components/Skeleton";
import { resolveLoader } from "./ModuleRegistry";
import { useDesktopStore } from "./store";
import { useDragMove } from "./useDragMove";
import { useResize, type ResizeDir } from "./useResize";

const RESIZE_DIRS: ResizeDir[] = ["n", "s", "e", "w", "ne", "nw", "se", "sw"];

const FALLBACK_MANIFEST = {
  id: "",
  name: "",
  version: "0",
  kind: "builtin" as const,
  entry: "",
  window: { w: 480, h: 320, minW: 360, minH: 240 },
};

/** 模块入口加载/渲染失败时的占位（容错：只影响这一扇窗，桌面不白屏）。 */
function ModulePlaceholder({ moduleId, reason }: { moduleId: string; reason?: string }) {
  return (
    <div className="win__placeholder" role="alert">
      <div className="win__placeholder-icon" aria-hidden="true">
        ⚠
      </div>
      <div className="win__placeholder-title">该模块尚未接入</div>
      <div className="win__placeholder-text">{reason ?? "模块入口缺失或加载失败。"}</div>
      <div className="win__placeholder-meta">module: {moduleId}</div>
    </div>
  );
}

interface BoundaryProps {
  moduleId: string;
  children: ReactNode;
}
interface BoundaryState {
  error?: Error;
}

export class ModuleErrorBoundary extends Component<BoundaryProps, BoundaryState> {
  state: BoundaryState = {};
  static getDerivedStateFromError(error: Error): BoundaryState {
    return { error };
  }
  render() {
    if (this.state.error) {
      return <ModulePlaceholder moduleId={this.props.moduleId} reason={this.state.error.message} />;
    }
    return this.props.children;
  }
}

interface Props {
  instanceId: string;
}

export function WindowFrame({ instanceId }: Props) {
  const win = useDesktopStore((s) => s.windows.find((w) => w.instanceId === instanceId));
  const topZ = useDesktopStore((s) => s.topZ);
  const focusWindow = useDesktopStore((s) => s.focusWindow);
  const minimizeWindow = useDesktopStore((s) => s.minimizeWindow);
  const closeWindow = useDesktopStore((s) => s.closeWindow);
  const toggleMaximize = useDesktopStore((s) => s.toggleMaximize);

  const elRef = useRef<HTMLDivElement>(null);
  const manifest = win ? useDesktopStore.getState().modules[win.moduleId]?.manifest : undefined;

  const dragHandler = useDragMove(instanceId, elRef);
  const resizeHandler = useResize(instanceId, elRef, manifest ?? FALLBACK_MANIFEST);

  const entry = manifest?.entry ?? "";
  const Lazy = useMemo(() => {
    if (!entry) {
      return lazy(() =>
        Promise.resolve({
          default: () => (
            <ModulePlaceholder moduleId={win?.moduleId ?? ""} reason="清单缺少 entry 字段" />
          ),
        }),
      );
    }
    return lazy(() =>
      resolveLoader(entry)().then((m) => {
        const pm = m.default;
        if (!pm || !pm.Component) {
          throw new Error("模块入口缺少 Component");
        }
        return { default: pm.Component };
      }),
    );
  }, [entry, win?.moduleId]);

  if (!win) return null;
  if (win.minimized) return null;

  const active = win.z === topZ;
  const name = manifest?.name ?? win.moduleId;

  return (
    <div
      ref={elRef}
      className={`win${active ? "" : " win--inactive"}${win.maximized ? " win--max" : ""}`}
      style={{
        left: win.geo.x,
        top: win.geo.y,
        width: win.geo.w,
        height: win.geo.h,
        zIndex: win.z,
      }}
      onPointerDown={() => focusWindow(instanceId)}
    >
      <div
        className="win__bar"
        onPointerDown={dragHandler}
        onDoubleClick={() => toggleMaximize(instanceId)}
        role="toolbar"
        aria-label={`窗口：${name}`}
        tabIndex={0}
      >
        <span className="win__title">{name}</span>
        <div className="win__controls">
          <button
            type="button"
            className="win__btn win__btn--min"
            aria-label="最小化"
            onPointerDown={(e) => e.stopPropagation()}
            onClick={() => minimizeWindow(instanceId)}
          >
            –
          </button>
          <button
            type="button"
            className="win__btn win__btn--max"
            aria-label={win.maximized ? "还原" : "最大化"}
            onPointerDown={(e) => e.stopPropagation()}
            onClick={() => toggleMaximize(instanceId)}
          >
            {win.maximized ? "❐" : "▢"}
          </button>
          <button
            type="button"
            className="win__btn win__btn--close"
            aria-label="关闭"
            onPointerDown={(e) => e.stopPropagation()}
            onClick={() => closeWindow(instanceId)}
          >
            ×
          </button>
        </div>
      </div>

      <div className="win__body">
        <ModuleErrorBoundary moduleId={win.moduleId}>
          <Suspense
            fallback={
              <div className="win__loading">
                <Skeleton height={120} />
              </div>
            }
          >
            <Lazy />
          </Suspense>
        </ModuleErrorBoundary>
      </div>

      {!win.maximized &&
        RESIZE_DIRS.map((dir) => (
          <div
            key={dir}
            className={`win__rz win__rz--${dir}`}
            onPointerDown={(e) => resizeHandler(e, dir)}
            aria-hidden="true"
          />
        ))}
    </div>
  );
}
