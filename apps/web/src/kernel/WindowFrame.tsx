import { Component, lazy, Suspense, useMemo, useRef } from "react";
import type { ReactNode } from "react";

import { Skeleton } from "@/shared/components/Skeleton";
import { resolveLoader } from "./ModuleRegistry";
import { useDesktopStore, zIndexOf } from "./store";
import { useDragMove } from "./useDragMove";
import { useResize, type ResizeDir } from "./useResize";
import { WindowInstanceContext } from "./windowInstance";

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
  const topPinZ = useDesktopStore((s) => s.topPinZ);
  const focusWindow = useDesktopStore((s) => s.focusWindow);
  const minimizeWindow = useDesktopStore((s) => s.minimizeWindow);
  const closeWindow = useDesktopStore((s) => s.closeWindow);
  const toggleMaximize = useDesktopStore((s) => s.toggleMaximize);
  const setPinned = useDesktopStore((s) => s.setPinned);
  const setFixedGeometry = useDesktopStore((s) => s.setFixedGeometry);

  const elRef = useRef<HTMLDivElement>(null);
  const manifest = win ? useDesktopStore.getState().modules[win.moduleId]?.manifest : undefined;

  // ★ T22：钉住时**干净地不挂**拖拽/缩放 ——
  //   hook 收到 enabled=false 会在任何副作用（preventDefault / setPointerCapture / 挂监听）**之前**返回；
  //   调用点也把 handler 从 onPointerDown 上摘掉、缩放手柄干脆不渲染（双保险）。
  const canDrag = !(win?.fixedGeometry ?? false);
  const dragHandler = useDragMove(instanceId, elRef, canDrag);
  const resizeHandler = useResize(instanceId, elRef, manifest ?? FALLBACK_MANIFEST, canDrag);

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

  // ★ T22：「当前窗」改为**按层判定** —— 每层各有一个最顶窗。
  //   置顶窗常驻最前；若沿用旧的全局 `win.z === topZ`，它会被永远算成 inactive（视觉上误判失焦）。
  const active = win.pinned ? win.pinZ === topPinZ : win.z === topZ;
  const name = manifest?.name ?? win.moduleId;

  return (
    <div
      ref={elRef}
      className={`win${active ? "" : " win--inactive"}${win.maximized ? " win--max" : ""}${
        win.pinned ? " win--pinned" : ""
      }${win.fixedGeometry ? " win--fixed" : ""}`}
      style={{
        left: win.geo.x,
        top: win.geo.y,
        width: win.geo.w,
        height: win.geo.h,
        // ★ 两段 Z 序：置顶窗在 [PIN_BASE, …)，普通窗仍是 z —— 两层不混算
        zIndex: zIndexOf(win),
      }}
      onPointerDown={() => focusWindow(instanceId)}
    >
      <div
        className="win__bar"
        onPointerDown={canDrag ? dragHandler : undefined}
        onDoubleClick={() => toggleMaximize(instanceId)}
        role="toolbar"
        aria-label={`窗口：${name}`}
        tabIndex={0}
      >
        <span className="win__title">{name}</span>
        <div className="win__controls">
          {/* ★ T22：两个新按钮加在「最小化 / 最大化 / 关闭」的**左侧** */}
          <button
            type="button"
            className={`win__btn win__btn--pin${win.pinned ? " is-on" : ""}`}
            aria-label={win.pinned ? "取消置顶" : "置顶"}
            aria-pressed={win.pinned}
            title={win.pinned ? "取消置顶" : "置顶（始终盖过普通窗口）"}
            onPointerDown={(e) => e.stopPropagation()}
            onClick={() => setPinned(instanceId, !win.pinned)}
          >
            ★
          </button>
          <button
            type="button"
            className={`win__btn win__btn--fix${win.fixedGeometry ? " is-on" : ""}`}
            aria-label={win.fixedGeometry ? "解除固定几何" : "固定位置与大小"}
            aria-pressed={win.fixedGeometry}
            title={win.fixedGeometry ? "解除固定几何" : "固定位置与大小（锁定，不可拖拽缩放）"}
            onPointerDown={(e) => e.stopPropagation()}
            onClick={() => setFixedGeometry(instanceId, !win.fixedGeometry)}
          >
            ▣
          </button>
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
            {/* ★ T22：把本窗的 instanceId 交给窗口内的插件（如"置顶本窗"按钮） */}
            <WindowInstanceContext.Provider value={instanceId}>
              <Lazy />
            </WindowInstanceContext.Provider>
          </Suspense>
        </ModuleErrorBoundary>
      </div>

      {/* ★ T22：固定几何时**缩放手柄整个不渲染**（不是渲染了再拦） */}
      {!win.maximized &&
        !win.fixedGeometry &&
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
