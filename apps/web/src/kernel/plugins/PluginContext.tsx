import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ComponentType,
  type ReactNode,
} from "react";

import { api } from "@/shared/api/client";
import {
  contributionsForSlot,
  registerContributions,
  unregisterContributions,
} from "../slots/contributions";
import { syncPluginsToStore } from "./PluginRegistry";
import type { PluginContextValue, PluginInfo, SlotContribution, SlotName } from "./types";

/** 动态 import 一个插件入口，取出它导出的 slots 贡献（通用回退，支持任意 entry）。 */
async function defaultLoadEntry(
  entry: string,
): Promise<{ default: { slots?: Partial<Record<SlotName, ComponentType>> } }> {
  return import(/* @vite-ignore */ entry) as unknown as Promise<{
    default: { slots?: Partial<Record<SlotName, ComponentType>> };
  }>;
}

type ApiClient = typeof api;

export interface PluginProviderProps {
  children: ReactNode;
  /** 注入自定义 API 客户端（测试用）。 */
  client?: ApiClient;
  /** 注入自定义入口加载器（测试用）。 */
  loadEntry?: (
    entry: string,
  ) => Promise<{ default: { slots?: Partial<Record<SlotName, ComponentType>> } }>;
}

/**
 * 插件上下文提供者（T14 · 前端总入口）。
 *
 * 挂载后：拉取 /api/v1/plugins → 同步进桌面 store（Dock 自动出现/置灰）→
 * 动态 import 各启用插件的入口收集插槽贡献。启用/禁用/安装/卸载都走后端 API，
 * 再刷新本地状态，全程不改内核业务代码（"一切皆插件"的落地）。
 *
 * 这是 T02 预留的集成缝：把 <PluginProvider> 包在桌面根组件外即可启用真实插件加载。
 */
export function PluginProvider({
  children,
  client = api,
  loadEntry = defaultLoadEntry,
}: PluginProviderProps) {
  const [plugins, setPlugins] = useState<PluginInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | undefined>(undefined);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(undefined);
    try {
      const data = await client.get<{ plugins: PluginInfo[] }>("/api/v1/plugins");
      const list = data.plugins;
      setPlugins(list);
      syncPluginsToStore(list);
      for (const p of list) {
        if (p.enabled && p.manifest.entry) {
          try {
            const mod = await loadEntry(p.manifest.entry);
            const slots = mod.default?.slots;
            if (slots) {
              const items: SlotContribution[] = (Object.keys(slots) as SlotName[]).map((slot) => ({
                slot,
                pluginId: p.id,
                component: slots[slot] as ComponentType,
              }));
              registerContributions(p.id, items);
            }
          } catch (e) {
            // 入口缺失或加载失败：不影响内核，仅该插件无 UI 贡献。
            // 但**不许静默**——否则"插件界面没出来"会变成查不出的悬案（实测踩过一次）。
            console.error(`[plugins] 插件「${p.id}」的入口加载失败：`, e);
          }
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [client, loadEntry]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const enable = useCallback(
    async (id: string) => {
      await client.post(`/api/v1/plugins/${id}/enable`);
      await refresh();
    },
    [client, refresh],
  );

  const disable = useCallback(
    async (id: string) => {
      await client.post(`/api/v1/plugins/${id}/disable`);
      await refresh();
    },
    [client, refresh],
  );

  const install = useCallback(
    async (id: string) => {
      await client.post("/api/v1/plugins/install", { id });
      await refresh();
    },
    [client, refresh],
  );

  const uninstall = useCallback(
    async (id: string) => {
      await client.post(`/api/v1/plugins/${id}/uninstall`);
      unregisterContributions(id);
      await refresh();
    },
    [client, refresh],
  );

  const getContributions = useCallback((slot: SlotName) => contributionsForSlot(slot), []);

  const value = useMemo<PluginContextValue>(
    () => ({
      plugins,
      loading,
      error,
      enable,
      disable,
      install,
      uninstall,
      refresh,
      getContributions,
    }),
    [plugins, loading, error, enable, disable, install, uninstall, refresh, getContributions],
  );

  return <PluginContext.Provider value={value}>{children}</PluginContext.Provider>;
}

export const PluginContext = createContext<PluginContextValue | null>(null);

/** 读取插件上下文（必须在 <PluginProvider> 内）。 */
export function usePlugins(): PluginContextValue {
  const ctx = useContext(PluginContext);
  if (!ctx) {
    throw new Error("usePlugins 必须在 <PluginProvider> 内使用");
  }
  return ctx;
}
