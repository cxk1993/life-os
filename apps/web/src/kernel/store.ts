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
  /**
   * ★ T22 置顶：进「置顶层」，渲染时始终盖过普通层。
   * `z` 仍只在普通层语义内维护 —— 两层计数不混算（见 PIN_BASE）。
   */
  pinned: boolean;
  /** ★ T22 固定几何：位置与大小锁定，不可拖拽、不可缩放。 */
  fixedGeometry: boolean;
  /** ★ 置顶层内的序号（由 topPinZ 分配）。未置顶时为 undefined。 */
  pinZ?: number;
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

/**
 * ★ T22：置顶层的 zIndex 偏移基数。
 * 取值远大于普通层可能达到的 z（普通层从 10 起、每操作 +1），
 * 从而保证「任何置顶窗的 zIndex > 任何普通窗的 zIndex」，两层**永不混算**。
 */
const PIN_BASE = 10000;

interface PersistedShape {
  windows: WindowState[];
  topZ: number;
  /** ★ 置顶层计数器（旧快照无此字段 → 默认 0）。 */
  topPinZ?: number;
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
      topPinZ: s.topPinZ,
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
  /** ★ T22：置顶层计数器（与 topZ 各管一层，互不干扰）。 */
  topPinZ: number;
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
  /** ★ T22：置顶开关（进/出置顶层）。 */
  setPinned: (instanceId: string, pinned: boolean) => void;
  /** ★ T22：固定几何开关（锁定位置与大小）。 */
  setFixedGeometry: (instanceId: string, fixed: boolean) => void;

  hydrate: () => void;
}

export const useDesktopStore = create<DesktopState>((set, get) => ({
  modules: {},
  windows: [],
  topZ: 10,
  topPinZ: 0,
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
      pinned: false,
      fixedGeometry: false,
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

  /**
   * ★ T22 置顶开关。
   * - **置顶**：进置顶层，取一个新的 `pinZ`（`topPinZ + 1`）→ 置顶层内部「后钉的在上」，
   *   且这个相对顺序**不会被后续点击聚焦打乱**（验收 #5）。
   * - **取消置顶**：回普通层。★ 同时把它在普通层的 `z` 提到最前 ——
   *   否则它按旧 `z` 沉到别的窗后面，"取消钉住"一按窗口当场消失，很困惑。
   */
  setPinned: (instanceId, pinned) => {
    set((s) => {
      const w = s.windows.find((x) => x.instanceId === instanceId);
      if (!w) return {};
      if (pinned) {
        const topPinZ = s.topPinZ + 1;
        return {
          topPinZ,
          windows: s.windows.map((x) =>
            x.instanceId === instanceId ? { ...x, pinned: true, pinZ: topPinZ } : x,
          ),
        };
      }
      const topZ = s.topZ + 1;
      return {
        topZ,
        windows: s.windows.map((x) =>
          x.instanceId === instanceId ? { ...x, pinned: false, pinZ: undefined, z: topZ } : x,
        ),
      };
    });
    savePersisted(get());
  },

  /**
   * ★ T22 固定几何开关。只改标记 ——
   * 拖拽/缩放由 `WindowFrame` 据此**条件不挂**（手柄不渲染、onPointerDown 不给）。
   */
  setFixedGeometry: (instanceId, fixed) => {
    set((s) => ({
      windows: s.windows.map((x) =>
        x.instanceId === instanceId ? { ...x, fixedGeometry: fixed } : x,
      ),
    }));
    savePersisted(get());
  },

  hydrate: () => {
    const persisted = loadPersisted();
    if (!persisted) return;
    // 快照损坏（windows 不是数组）→ 当作没有，不要崩
    if (!Array.isArray(persisted.windows)) return;
    const s = get();
    // 只恢复仍注册且启用的模块的窗口
    // ★ 向后兼容（验收 #4）：旧快照没有 pinned / fixedGeometry / pinZ / topPinZ ——
    //   缺字段一律安全降级（false / undefined / 0），**绝不因缺字段丢窗口或抛错**。
    const windows = persisted.windows
      .filter((w) => {
        const reg = s.modules[w.moduleId];
        return reg && reg.enabled;
      })
      .map((w) => ({
        ...w,
        pinned: w.pinned === true,
        fixedGeometry: w.fixedGeometry === true,
        pinZ: typeof w.pinZ === "number" ? w.pinZ : undefined,
      }));
    // topPinZ 缺失时按已恢复窗口的最大 pinZ 兜底，保证置顶层顺序能接着排
    const maxPinZ = windows.reduce(
      (mx, w) => (typeof w.pinZ === "number" ? Math.max(mx, w.pinZ) : mx),
      0,
    );
    set({
      windows,
      topZ: persisted.topZ ?? 10,
      topPinZ: persisted.topPinZ ?? maxPinZ,
      seq: persisted.seq ?? 0,
    });
  },
}));

/**
 * ★ T22 渲染用 zIndex。
 * 置顶窗落在 `[PIN_BASE, …)`，普通窗仍是原来的 `z` —— **两层永不混算**：
 * 任何置顶窗的 zIndex 都大于任何普通窗的 zIndex。
 */
export function zIndexOf(w: WindowState): number {
  return w.pinned ? PIN_BASE + (w.pinZ ?? 0) : w.z;
}

/**
 * ★ T22：「当前窗」判定 —— **普通层**里 z 最高的那扇（置顶窗不参与）。
 *
 * `closeTopmost()` 与 `cycleWindow()` 共用这一条规则，避免两处各写一份而走偏。
 * 置顶窗常驻最前，若参与"当前窗"判定，快捷键会永远命中置顶那个而不是用户在看的那扇。
 */
export function topmostNormalId(windows: WindowState[]): string | null {
  let topId: string | null = null;
  let topZ = -Infinity;
  for (const w of windows) {
    if (w.pinned) continue;
    if (w.z > topZ) {
      topZ = w.z;
      topId = w.instanceId;
    }
  }
  return topId;
}

/** ★ T22：普通层按 z 升序（最底在前）。供 `cycleWindow()` 用。 */
export function normalStack(windows: WindowState[]): WindowState[] {
  return windows
    .filter((w) => !w.pinned)
    .slice()
    .sort((a, b) => a.z - b.z);
}

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

export { snap, TOPBAR, DOCK, PIN_BASE };
