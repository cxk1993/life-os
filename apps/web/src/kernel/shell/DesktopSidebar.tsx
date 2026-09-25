import { useEffect, useState } from "react";

import { PluginBoundary } from "../plugins/PluginBoundary";
import { useSlotContributions } from "../slots/contributions";
import { useDesktopStore } from "../store";

/**
 * U3 · 桌面级双侧栏（副总监拍案 1 号：U3 视图侧 → Doubao；schema 知默已会签）。
 *
 * 桌面级 `desktop.dock-left` / `desktop.dock-right` —— E5 `window.sidecar` 的桌面级兄弟，
 * 同一贡献机制（useSlotContributions），两级挂载点。
 *
 * 判据要点（K1-K8 + 业界，workbuddy《UI 四方向》背书）：
 *   K1 折叠持久化（localStorage，刷新保持）
 *   K2 折叠态留可见把手（toggle「obvious and persistent」）
 *   K3 折叠态带 tooltip（纯图标无标签 = 学习税）
 *   K4 aria-expanded / 可见 focus 环 / Escape 展开（可访问性）
 *   K5 左=导航/结构、右=摘要/情境（业界惯例，右栏是今日摘要/待办/健康趋势的天生居民）
 *   K6 无贡献零渲染不占位（同 E5 J4 铁律）
 *   K7 每贡献 PluginBoundary 独立兜错（单个插件炸只灰自己）
 *   K8 折叠后不占布局位（窗口区域最大化）
 */

const COLLAPSE_KEY: Record<"left" | "right", string> = {
  left: "lifeos.dock-left.collapsed",
  right: "lifeos.dock-right.collapsed",
};

function usePersistedCollapse(side: "left" | "right"): [boolean, () => void] {
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem(COLLAPSE_KEY[side]) === "1";
    } catch {
      return false;
    }
  });
  // ★ 令 96/97：罗盘（Desktop）经 CustomEvent 统一操控侧栏 —— 本组件同步响应。
  useEffect(() => {
    const onCompass = (e: Event) => {
      const d = (e as CustomEvent<{ side: "left" | "right"; collapsed: boolean }>).detail;
      if (d && d.side === side) setCollapsed(d.collapsed);
    };
    window.addEventListener("lifeos:sidebar-collapse", onCompass);
    return () => window.removeEventListener("lifeos:sidebar-collapse", onCompass);
  }, [side]);
  const toggle = () => {
    setCollapsed((v) => {
      const next = !v;
      try {
        localStorage.setItem(COLLAPSE_KEY[side], next ? "1" : "0");
      } catch {
        /* localStorage 不可用时仅本次会话生效 */
      }
      return next;
    });
  };
  return [collapsed, toggle];
}

/** 左侧栏内置居民：模块导航（左=导航/结构惯例，复用 modules store，与 Dock 同源）。 */
export function DesktopSideNav() {
  const modules = useDesktopStore((s) => s.modules);
  const openWindow = useDesktopStore((s) => s.openWindow);
  const list = Object.entries(modules)
    .filter(([, r]) => r.enabled)
    .map(([id, r]) => ({ id, manifest: r.manifest }))
    .sort((a, b) => (a.manifest.name ?? a.id).localeCompare(b.manifest.name ?? b.id));
  return (
    <div className="desktop-side__nav" data-testid="desktop-side-nav">
      <div className="desktop-side__title">导航</div>
      {list.length === 0 ? (
        <div className="desktop-side__empty">暂无模块</div>
      ) : (
        <ul className="desktop-side__nav-list">
          {list.map((r) => (
            <li key={r.id}>
              <button
                type="button"
                onClick={() => openWindow(r.id)}
                aria-label={`打开${r.manifest.name ?? r.id}`}
              >
                <span className="desktop-side__today-icon">{r.manifest.icon ?? "·"}</span>
                {r.manifest.name ?? r.id}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** 右侧栏内置居民：今日摘要（复用 U2 四源聚合，桌面级常驻）。 */
export function DesktopTodaySummary() {
  const openWindow = useDesktopStore((s) => s.openWindow);
  // 简化版：只列四个插件的「有/无」状态，细节交给 U2 面板与各插件窗
  const sources = [
    { id: "calendar", label: "日程", icon: "历" },
    { id: "todo", label: "待办", icon: "待" },
    { id: "diary", label: "日记", icon: "日" },
    { id: "review", label: "复盘", icon: "复" },
  ];
  return (
    <div className="desktop-side__today" data-testid="desktop-today-summary">
      <div className="desktop-side__title">今日</div>
      <ul className="desktop-side__today-list">
        {sources.map((s) => (
          <li key={s.id}>
            <button type="button" onClick={() => openWindow(s.id)} aria-label={`打开${s.label}`}>
              <span className="desktop-side__today-icon">{s.icon}</span>
              {s.label}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** U3 桌面级侧栏容器：折叠持久化 + slot 贡献渲染。 */
export function DesktopSidebar({ side }: { side: "left" | "right" }) {
  const slot: "desktop.dock-left" | "desktop.dock-right" =
    side === "left" ? "desktop.dock-left" : "desktop.dock-right";
  const items = useSlotContributions(slot);
  const [collapsed, toggle] = usePersistedCollapse(side);

  // K4：折叠态下 Escape 展开
  useEffect(() => {
    if (!collapsed) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") toggle();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [collapsed, toggle]);

  const label = side === "left" ? "左侧栏" : "右侧栏";
  const cls = `desktop-sidebar desktop-sidebar--${side}${collapsed ? " is-collapsed" : ""}`;

  return (
    <aside
      className={cls}
      data-sidebar={side}
      data-testid={`desktop-sidebar-${side}`}
      aria-label={label}
      aria-expanded={!collapsed}
    >
      <button
        type="button"
        className="desktop-sidebar__toggle"
        aria-label={collapsed ? `展开${label}` : `收起${label}`}
        title={collapsed ? `展开${label}` : `收起${label}`}
        onClick={toggle}
      >
        {side === "left" ? (collapsed ? "⟩" : "⟨") : collapsed ? "⟨" : "⟩"}
      </button>
      {!collapsed && (
        <div className="desktop-sidebar__body">
          {side === "left" ? (
            <>
              {/* ★ 主人反馈修复（2026-09-25）：「侧栏自定义容器」加不进/看不到 ——
                  根因：左栏被内置导航（全模块列表，当前 23 项）**占满**，用户的
                  slot 贡献被挤到最下方看不见。
                  → **用户自定义项优先置顶**；**内置导航改 <details> 可折叠小节**
                    （默认：有用户项时收起，没用户项时展开 —— 不丢可达性）。 */}
              {items.length === 0 ? null : (
                <div className="desktop-sidebar__slots" data-testid="desktop-sidebar-slots">
                  {items.map((c, i) => (
                    <PluginBoundary key={`${c.pluginId}:${i}`} pluginId={c.pluginId}>
                      <c.component />
                    </PluginBoundary>
                  ))}
                </div>
              )}
              <details className="desktop-side__nav-fold" open={items.length === 0}>
                <summary className="desktop-side__fold-summary">模块导航</summary>
                <DesktopSideNav />
              </details>
            </>
          ) : (
            <>
              <DesktopTodaySummary />
              {items.length === 0 ? null : (
                <div className="desktop-sidebar__slots">
                  {items.map((c, i) => (
                    <PluginBoundary key={`${c.pluginId}:${i}`} pluginId={c.pluginId}>
                      <c.component />
                    </PluginBoundary>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </aside>
  );
}
