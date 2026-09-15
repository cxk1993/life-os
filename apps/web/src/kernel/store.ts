import { create } from "zustand";

import type { ModuleManifest } from "./types";

/**
 * 桌面状态中枢（Zustand）。
 *
 * 管两件事：
 *   1. 模块注册表（来自 modules.json，由 ModuleRegistry 写入）。
 *   2. 窗口生命周期（open/close/focus/min/max/z-index）与几何持久化。
 *
 * 几何存 localStorage，刷新后由 Desktop 调 hydrate() 恢复。
 * 这是「注册表与运行时分离」的最小实现，方便将来热插拔（T14）。
 */

export interface WinGeo {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface WindowState {
  instanceId: string;
  moduleId: string;
  z: number;
  minimized: boolean;
  maximized: boolean;
  geo: WinGeo;
  /** 最大化前的几何，用于还原。 */
  _prev?: WinGeo;
}

export interface ModuleReg {
  manifest: ModuleManifest;
  enabled: boolean;
  error?: string;
}

const TOPBAR = 48;
const DOCK = 64;
const SNAP = 8;
const STORE_KEY = "lifeos.windows.v1";

interface PersistedShape {
  windows: WindowState[];
  topZ: number;
  seq: number;
  enabled: Record<string, boolean>;
}

function vw(): number {
  return typeof window !== "undefined" && window.innerWidth ? window.innerWidth : 1280;
}
function vh(): number {
  return typeof window !== "undefined" && window.innerHeight ? window.innerHeight : 800;
}

function snap(v: number): number {
  return Math.round(v / SNAP) * SNAP;
}

function clampGeo(g: WinGeo, manifest: ModuleManifest): WinGeo {
  const minW = manifest.window.minW ?? 360;
  const minH = manifest.window.minH ?? 240;
  const w = Math.max(minW, Math.round(g.w));
  const h = Math.max(minH, Math.round(g.h));
  const maxX = Math.max(0, vw() - w);
  const maxY = Math.max(TOPBAR, vh() - DOCK - h);
  const x = Math.min(Math.max(0, Math.round(g.x)), maxX);
  const y = Math.min(Math.max(TOPBAR, Math.round(g.y)), maxY);
  return { x, y, w, h };
}

function fullGeo(): WinGeo {
  return { x: 0, y: TOPBAR, w: vw(), h: Math.max(240, vh() - TOPBAR - DOCK) };
}

function defaultGeo(manifest: ModuleManifest, seq: number): WinGeo {
  const spec = manifest.window;
  if (typeof spec.x === "number" && typeof spec.y === "number") {
    return clampGeo({ x: spec.x, y: spec.y, w: spec.w, h: spec.h }, manifest);
  }
  const off = 48 + (seq % 6) * 28;
  return clampGeo({ x: off, y: TOPBAR + off, w: spec.w, h: spec.h }, manifest);
}

function loadPersisted(): PersistedShape | null {
  try {
    const raw = localStorage.getItem(STORE_KEY);
    return raw ? (JSON.parse(raw) as PersistedShape) : null;
  } catch {
    return null;
  }
}

function savePersisted(s: DesktopState): void {
  try {
    const enabled: Record<string, boolean> = {};
    for (const id in s.modules) enabled[id] = s.modules[id].enabled;
    const data: PersistedShape = {
      windows: s.windows,
      topZ: s.topZ,
      seq: s.seq,
      enabled,
    };
    localStorage.setItem(STORE_KEY, JSON.stringify(data));
  } catch {
    /* 存储不可用时忽略 */
  }
}

export interface DesktopState {
  modules: Record<string, ModuleReg>;
  windows: WindowState[];
  topZ: number;
  seq: number;

  registerModule: (m: ModuleManifest) => void;
  unregisterModule: (id: string) => void;
  enableModule: (id: string) => void;
  disableModule: (id: string) => void;

  openWindow: (moduleId: string) => void;
  closeWindow: (instanceId: string) => void;
  focusWindow: (instanceId: string) => void;
  minimizeWindow: (instanceId: string) => void;
  restoreWindow: (instanceId: string) => void;
  toggleMaximize: (instanceId: string) => void;
  setGeo: (instanceId: string, patch: Partial<WinGeo>) => void;
  tidyDesktop: () => void;

  hydrate: () => void;
}

export const useDesktopStore = create<DesktopState>((set, get) => ({
  modules: {},
  windows: [],
  topZ: 10,
  seq: 0,

  registerModule: (m) => {
    const persisted = loadPersisted();
    const enabled = persisted?.enabled[m.id] ?? true;
    set((s) => ({
      modules: { ...s.modules, [m.id]: { manifest: m, enabled } },
    }));
  },

  unregisterModule: (id) => {
    set((s) => {
      const next = { ...s.modules };
      delete next[id];
      return {
        modules: next,
        windows: s.windows.filter((w) => w.moduleId !== id),
      };
    });
    savePersisted(get());
  },

  enableModule: (id) => {
    set((s) => {
      const reg = s.modules[id];
      if (!reg) return {};
      return { modules: { ...s.modules, [id]: { ...reg, enabled: true, error: undefined } } };
    });
    savePersisted(get());
  },

  disableModule: (id) => {
    set((s) => {
      const reg = s.modules[id];
      if (!reg) return {};
      return { modules: { ...s.modules, [id]: { ...reg, enabled: false } } };
    });
    savePersisted(get());
  },

  openWindow: (moduleId) => {
    const s = get();
    const reg = s.modules[moduleId];
    if (!reg || !reg.enabled) return;
    const manifest = reg.manifest;

    if (manifest.window.singleton) {
      const existing = s.windows.find((w) => w.moduleId === moduleId);
      if (existing) {
        get().restoreWindow(existing.instanceId);
        get().focusWindow(existing.instanceId);
        return;
      }
    }

    const seq = s.seq + 1;
    const topZ = s.topZ + 1;
    const geo = defaultGeo(manifest, seq);
    const inst: WindowState = {
      instanceId: `${moduleId}#${seq}`,
      moduleId,
      z: topZ,
      minimized: false,
      maximized: false,
      geo,
    };
    set((st) => ({ windows: [...st.windows, inst], topZ, seq }));
    savePersisted(get());
  },

  closeWindow: (instanceId) => {
    set((s) => ({ windows: s.windows.filter((w) => w.instanceId !== instanceId) }));
    savePersisted(get());
  },

  focusWindow: (instanceId) => {
    set((s) => {
      const w = s.windows.find((x) => x.instanceId === instanceId);
      if (!w) return {};
      const topZ = s.topZ + 1;
      return {
        topZ,
        windows: s.windows.map((x) =>
          x.instanceId === instanceId ? { ...x, z: topZ, minimized: false } : x,
        ),
      };
    });
    savePersisted(get());
  },

  minimizeWindow: (instanceId) => {
    set((s) => ({
      windows: s.windows.map((x) => (x.instanceId === instanceId ? { ...x, minimized: true } : x)),
    }));
    savePersisted(get());
  },

  restoreWindow: (instanceId) => {
    set((s) => ({
      windows: s.windows.map((x) => (x.instanceId === instanceId ? { ...x, minimized: false } : x)),
    }));
    savePersisted(get());
  },

  toggleMaximize: (instanceId) => {
    set((s) => {
      const w = s.windows.find((x) => x.instanceId === instanceId);
      if (!w) return {};
      const topZ = s.topZ + 1;
      if (w.maximized && w._prev) {
        return {
          topZ,
          windows: s.windows.map((x) =>
            x.instanceId === instanceId ? { ...x, maximized: false, geo: w._prev!, z: topZ } : x,
          ),
        };
      }
      return {
        topZ,
        windows: s.windows.map((x) =>
          x.instanceId === instanceId
            ? { ...x, maximized: true, _prev: x.geo, geo: fullGeo(), z: topZ }
            : x,
        ),
      };
    });
    savePersisted(get());
  },

  setGeo: (instanceId, patch) => {
    set((s) => {
      const w = s.windows.find((x) => x.instanceId === instanceId);
      if (!w) return {};
      const merged = { ...w.geo, ...patch };
      const geo = w.maximized ? merged : clampGeo(merged, fallbackManifest(w.moduleId, s));
      return {
        windows: s.windows.map((x) => (x.instanceId === instanceId ? { ...x, geo } : x)),
      };
    });
    savePersisted(get());
  },

  tidyDesktop: () => {
    set((s) => {
      let seq = s.seq;
      const windows = s.windows.map((w) => {
        seq += 1;
        const manifest = s.modules[w.moduleId]?.manifest;
        const geo = manifest ? defaultGeo(manifest, seq) : w.geo;
        return { ...w, minimized: false, maximized: false, _prev: undefined, geo };
      });
      return { windows, seq };
    });
    savePersisted(get());
  },

  hydrate: () => {
    const persisted = loadPersisted();
    if (!persisted) return;
    const s = get();
    // 只恢复仍注册且启用的模块的窗口
    const windows = persisted.windows.filter((w) => {
      const reg = s.modules[w.moduleId];
      return reg && reg.enabled;
    });
    set({ windows, topZ: persisted.topZ, seq: persisted.seq });
  },
}));

function fallbackManifest(moduleId: string, s: DesktopState): ModuleManifest {
  const reg = s.modules[moduleId];
  if (reg) return reg.manifest;
  return {
    id: moduleId,
    name: moduleId,
    version: "0",
    kind: "builtin",
    entry: "",
    window: { w: 480, h: 320 },
  };
}

export { snap, TOPBAR, DOCK };
