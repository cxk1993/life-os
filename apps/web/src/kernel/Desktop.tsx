import { useEffect, useMemo, useState } from "react";

import { ToastHost } from "@/shared/components/Toast";
import { initTheme } from "@/shared/styles/theme";
import { pluginHost, registerModules } from "./ModuleRegistry";
import { useDesktopStore, normalStack, topmostNormalId, type WindowState } from "./store";
import { installIframeAuthBridge } from "./iframeAuthBridge";
import type { ModuleManifest } from "./types";
import { AuthGate } from "./AuthGate";
import { logout } from "@/shared/api/auth";
import { Dock } from "./Dock";
import { useShortcuts, type ShortcutHandlers } from "./Shortcuts";
import { TopBar } from "./TopBar";
import { WindowManager } from "./WindowManager";

const MODULES_URL = "/modules.json";

/**
 * ★ T23：只取**当前工作区**的窗口 —— 快捷键作用于"你正在看的那个桌面"。
 * 否则快捷键会命中隐藏工作区里的窗，出现"关了个看不见的东西"。
 */
function activeWindows(): WindowState[] {
  const s = useDesktopStore.getState();
  return s.windows.filter((w) => w.workspaceId === s.activeWorkspaceId);
}

/**
 * 关闭 z-index 最高的窗口（即当前聚焦窗口）。
 *
 * ★ T22：「当前窗」判定**按层**做 —— 置顶窗不参与（契约：「置顶窗不参与'当前窗'判定」）。
 * 否则置顶窗的 zIndex 恒高于普通窗，这个快捷键会永远关掉置顶那个，
 * 而不是用户正在看的那一个（症状："关窗口关错人"）。
 * ★ T23：再加上"只在本工作区内"。
 * ★ 规则抽到 `store.topmostNormalId()`，与 `cycleWindow` 共用同一条判定。
 */
function closeTopmost(): void {
  const s = useDesktopStore.getState();
  const topId = topmostNormalId(activeWindows());
  if (topId) s.closeWindow(topId);
}

/**
 * 在打开的窗口间循环聚焦（把最顶层下面的那扇提到最前）。
 *
 * ★ T22：与 `closeTopmost` 是**同一条判定的两处应用** ——
 * "把某一扇提到最前"是**普通层**的叠放操作；置顶层顺序由 `pinZ` 决定，
 * 聚焦改不动它，所以置顶层不参与循环。卡里只点名了 `closeTopmost`，此处按同一判定处理。
 * ★ T23：同样限定在当前工作区内。
 */
function cycleWindow(): void {
  const s = useDesktopStore.getState();
  const stack = normalStack(activeWindows());
  if (stack.length === 0) return;
  const below = stack.length > 1 ? stack[stack.length - 2] : stack[0];
  s.focusWindow(below.instanceId);
}

/**
 * 桌面容器：顶栏 + 窗口层 + 坞 + 全局搜索 + Toast。
 * 启动时拉取 modules.json 注册模块，并 hydrate 已持久化的窗口几何。
 */
export function Desktop() {
  const [searchOpen, setSearchOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIdx, setActiveIdx] = useState(0);
  const tidy = useDesktopStore((s) => s.tidyDesktop);
  const modules = useDesktopStore((s) => s.modules);

  useEffect(() => {
    initTheme();
    // ★ B2：跨源自家 iframe 的登录态握手桥（origin 白名单空起步，fail closed）
    const bridge = installIframeAuthBridge();
    let cancelled = false;
    fetch(MODULES_URL)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((list: ModuleManifest[]) => {
        if (cancelled) return;
        registerModules(list);
        useDesktopStore.getState().hydrate();
      })
      .catch(() => {
        /* 没有 modules.json：桌面为空，但不白屏（内核不依赖任何具体模块） */
      });
    return () => {
      cancelled = true;
      bridge.dispose();
    };
  }, []);

  const openSearch = () => {
    setQuery("");
    setActiveIdx(0);
    setSearchOpen(true);
  };
  const closeSearch = () => setSearchOpen(false);

  const handlers: ShortcutHandlers = {
    onToggleSearch: openSearch,
    onEscape: () => {
      if (searchOpen) closeSearch();
      else closeTopmost();
    },
    onCloseWindow: closeTopmost,
    onCycleWindow: cycleWindow,
  };
  useShortcuts(handlers);

  const items = useMemo(() => {
    const q = query.trim().toLowerCase();
    return Object.values(modules)
      .filter((r) => r.enabled)
      .map((r) => r.manifest)
      .filter((m) => !q || m.name.toLowerCase().includes(q) || m.id.toLowerCase().includes(q));
  }, [query, modules]);

  return (
    <AuthGate>
      <div className="desktop">
        <TopBar onOpenSearch={openSearch} onTidy={tidy} onLogout={() => void logout()} />
        <div className="windows">
          <WindowManager />
        </div>
        <Dock />
        <ToastHost />

        {searchOpen ? (
          <>
            <div className="search-backdrop" onClick={closeSearch} />
            <div className="search" role="dialog" aria-modal="true" aria-label="全局搜索">
              <input
                className="search__input"
                autoFocus
                placeholder="搜索模块…"
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setActiveIdx(0);
                }}
                onKeyDown={(e) => {
                  if (e.key === "ArrowDown") {
                    e.preventDefault();
                    setActiveIdx((i) => Math.min(items.length - 1, i + 1));
                  } else if (e.key === "ArrowUp") {
                    e.preventDefault();
                    setActiveIdx((i) => Math.max(0, i - 1));
                  } else if (e.key === "Enter") {
                    const m = items[activeIdx];
                    if (m) {
                      closeSearch();
                      pluginHost.open(m.id);
                    }
                  } else if (e.key === "Escape") {
                    e.stopPropagation(); // ★ BUG-T02-1：Esc 只关搜索层，不许冒泡成"关窗"
                    closeSearch();
                  }
                }}
              />
              <div className="search__list">
                {items.length ? (
                  items.map((m, i) => (
                    <div
                      key={m.id}
                      className={`search__item${i === activeIdx ? " search__item--active" : ""}`}
                      onMouseEnter={() => setActiveIdx(i)}
                      onClick={() => {
                        closeSearch();
                        pluginHost.open(m.id);
                      }}
                    >
                      {m.name}
                    </div>
                  ))
                ) : (
                  <div className="search__empty">没有匹配的模块</div>
                )}
              </div>
            </div>
          </>
        ) : null}
      </div>
    </AuthGate>
  );
}
