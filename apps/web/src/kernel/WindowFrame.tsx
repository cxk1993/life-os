import { Component, lazy, Suspense, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";

import { Skeleton } from "@/shared/components/Skeleton";
import { resolveLoader } from "./ModuleRegistry";
import { useDesktopStore, workspaceOf, zIndexOf } from "./store";
import { useDragMove } from "./useDragMove";
import { useResize, type ResizeDir } from "./useResize";
import { WindowInstanceContext } from "./windowInstance";
import { useSlotContributions } from "./slots/contributions";
import { PluginBoundary } from "./plugins/PluginBoundary";

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

/**
 * E5：窗口侧栏（`window.sidecar` 扩展点）。
 * - attachTo = 目标窗口 moduleId；缺省贡献在所有窗口渲染。
 * - ★ 无匹配贡献时**零渲染**（不占位、不影响布局）——判据 J4。
 */
function SidecarSlot({ moduleId }: { moduleId: string }) {
  const items = useSlotContributions("window.sidecar");
  const matched = items.filter((c) => !c.attachTo || c.attachTo === moduleId);
  if (matched.length === 0) return null;
  return (
    <aside className="win__sidecar" data-sidecar-for={moduleId} aria-label="窗口侧栏">
      {matched.map((c, i) => (
        <PluginBoundary key={`${c.pluginId}:${i}`} pluginId={c.pluginId}>
          <c.component />
        </PluginBoundary>
      ))}
    </aside>
  );
}
export { SidecarSlot };

export function WindowFrame({ instanceId }: Props) {
  const win = useDesktopStore((s) => s.windows.find((w) => w.instanceId === instanceId));
  // ★ T23：「当前窗」判定要用的两个计数器，取自**该窗所属工作区**（顶层已无全局计数器）
  const ws = useDesktopStore((s) => workspaceOf(s, instanceId));
  const activeWorkspaceId = useDesktopStore((s) => s.activeWorkspaceId);
  const focusWindow = useDesktopStore((s) => s.focusWindow);
  const minimizeWindow = useDesktopStore((s) => s.minimizeWindow);
  const closeWindow = useDesktopStore((s) => s.closeWindow);
  const toggleMaximize = useDesktopStore((s) => s.toggleMaximize);
  const setPinned = useDesktopStore((s) => s.setPinned);
  const setFixedGeometry = useDesktopStore((s) => s.setFixedGeometry);
  // ★ T23：标题栏右键「移到工作区…」
  const workspaces = useDesktopStore((s) => s.workspaces);
  const moveWindowToWorkspace = useDesktopStore((s) => s.moveWindowToWorkspace);
  const [menuAt, setMenuAt] = useState<{ x: number; y: number } | null>(null);

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

  // ★ T22：「当前窗」按**层**判定 —— 每层各有一个最顶窗。
  // ★ T23：再加一维 —— 两个计数器取自**该窗所属工作区**，所以是「层 × 工作区」两维判定。
  const active = win.pinned ? win.pinZ === (ws?.topPinZ ?? -1) : win.z === (ws?.topZ ?? -1);
  // ★ T23：不属于当前工作区的窗 **保持挂载**，只加隐藏类。
  //   ★ 绝对不能在 WindowManager 里把它从渲染树摘掉 —— 卸载 = iframe 重载 = 登录态丢失（契约 #4 / 验收 #6）。
  const hidden = win.workspaceId !== activeWorkspaceId;
  const name = manifest?.name ?? win.moduleId;

  return (
    <div
      ref={elRef}
      className={`win${active ? "" : " win--inactive"}${win.maximized ? " win--max" : ""}${
        win.pinned ? " win--pinned" : ""
      }${win.fixedGeometry ? " win--fixed" : ""}${hidden ? " win--hidden" : ""}`}
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
        onContextMenu={(e) => {
          // ★ T23：右键 → 「移到工作区…」
          e.preventDefault();
          setMenuAt({ x: e.clientX, y: e.clientY });
        }}
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
        {/* E5：窗口侧栏（无贡献时零渲染，不占位） */}
        <SidecarSlot moduleId={win.moduleId} />
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

      {/*
        ★ T23：标题栏右键 → 「移到工作区…」。
        ★ 用 portal 渲染到 body —— `.win` 上有 `overflow: hidden`，
          菜单若留在窗内，超出窗口的部分会被裁掉（拖拽时 `.win` 还有 transform，
          会把 fixed 的包含块也变成它自己）。portal 一次性绕开这两件事。
        ★ 最小集：只列**其它**工作区；没有别的就提示"先新建一个"。
      */}
      {menuAt &&
        createPortal(
          <>
            <div className="win__menu-veil" onPointerDown={() => setMenuAt(null)} />
            <div
              className="win__menu"
              style={{ left: menuAt.x, top: menuAt.y }}
              role="menu"
              aria-label="窗口菜单"
            >
              <div className="win__menu-title">移到工作区…</div>
              {workspaces.filter((k) => k.id !== win.workspaceId).length === 0 ? (
                <div className="win__menu-empty">还没有别的工作区</div>
              ) : (
                workspaces
                  .filter((k) => k.id !== win.workspaceId)
                  .map((k) => (
                    <button
                      key={k.id}
                      type="button"
                      role="menuitem"
                      className="win__menu-item"
                      onClick={() => {
                        moveWindowToWorkspace(instanceId, k.id);
                        setMenuAt(null);
                      }}
                    >
                      {k.name}
                    </button>
                  ))
              )}
            </div>
          </>,
          document.body,
        )}
    </div>
  );
}
