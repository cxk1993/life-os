import { useDesktopStore } from "./store";
import type { ModuleManifest, PluginModule } from "./types";

/**
 * 模块注册表（T02 这一版的实现）。
 *
 * 职责：
 *   - 把 modules.json 里的清单注册进桌面 store。
 *   - 提供「入口 → 动态 import 加载器」的解析（React.lazy 用）。
 *
 * 接口形状刻意与 T14 的 PluginHost 对齐（方法名一致），
 * 将来 T14 做真实插件发现/生命周期时，可直接顶替，不需要返工。
 *
 * 注意：本文件只加载「入口」，不认识任何业务；入口抛错由 WindowFrame
 * 的错误边界兜底（只该窗口占位，桌面不白屏）。
 */

/** 显式 entry → loader（mock 演示用，确定性、可被 Tree-shaking 分析）。 */
const ENTRY_LOADERS: Record<string, () => Promise<{ default: PluginModule }>> = {
  "@mocks/alpha": () => import("@/shared/mocks/alpha"),
  "@mocks/beta": () => import("@/shared/mocks/beta"),
  "@mocks/gamma": () => import("@/shared/mocks/gamma"),
  "@mocks/delta": () => import("@/shared/mocks/delta"),
  "@mocks/broken": () => import("@/shared/mocks/broken"),
};

/** 把 entry 说明符解析成 React.lazy 可用的 loader。 */
export function resolveLoader(entry: string): () => Promise<{ default: PluginModule }> {
  const explicit = ENTRY_LOADERS[entry];
  if (explicit) return explicit;
  // 通用回退：允许运行时给定的任意 entry（@vite-ignore 告诉打包器不要静态分析）。
  return () => import(/* @vite-ignore */ entry) as Promise<{ default: PluginModule }>;
}

export interface PluginHost {
  register(manifest: ModuleManifest): void;
  unregister(id: string): void;
  open(id: string, opts?: unknown): void;
  enable(id: string): void;
  disable(id: string): void;
}

export const pluginHost: PluginHost = {
  register: (m) => useDesktopStore.getState().registerModule(m),
  unregister: (id) => useDesktopStore.getState().unregisterModule(id),
  open: (id) => useDesktopStore.getState().openWindow(id),
  enable: (id) => useDesktopStore.getState().enableModule(id),
  disable: (id) => useDesktopStore.getState().disableModule(id),
};

/** 从清单数组批量注册（Desktop 在启动时调用）。 */
export function registerModules(list: ModuleManifest[]): void {
  const store = useDesktopStore.getState();
  list.forEach((m) => store.registerModule(m));
}
