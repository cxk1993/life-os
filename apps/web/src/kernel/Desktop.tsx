import { useEffect, useMemo, useState } from "react";

import { ToastHost } from "@/shared/components/Toast";
import { initTheme } from "@/shared/styles/theme";
import { pluginHost, registerModules } from "./ModuleRegistry";
import { useDesktopStore } from "./store";
import type { ModuleManifest } from "./types";
import { Dock } from "./Dock";
import { useShortcuts, type ShortcutHandlers } from "./Shortcuts";
import { TopBar } from "./TopBar";
import { WindowManager } from "./WindowManager";

const MODULES_URL = "/modules.json";

/** 关闭 z-index 最高的窗口（即当前聚焦窗口）。 */
function closeTopmost(): void {
  const s = useDesktopStore.getState();
  let topId: string | null = null;
  let topZ = -1;
  for (const w of s.windows) {
    if (w.z > topZ) {
      topZ = w.z;
      topId = w.instanceId;
    }
  }
  if (topId) s.closeWindow(topId);
}

/** 在打开的窗口间循环聚焦（把最顶层下面的那扇提到最前）。 */
function cycleWindow(): void {
  const s = useDesktopStore.getState();
  if (s.windows.length === 0) return;
  const sorted = [...s.windows].sort((a, b) => a.z - b.z);
  const below = sorted.length > 1 ? sorted[sorted.length - 2] : sorted[0];
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
    <div className="desktop">
      <TopBar onOpenSearch={openSearch} onTidy={tidy} />
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
  );
}
