import { useMemo, useSyncExternalStore } from "react";
import { useDesktopStore } from "../store";
import type { ModuleReg } from "../store";
import type { SlotContribution, SlotName } from "../plugins/types";

/**
 * 插槽贡献注册表（T14 · 前端侧）。
 *
 * 插件入口在求值期调用 registerContributions 登记它的插槽贡献；
 * 内核（SlotHost / useSlotContributions）按需取出"已启用且声明合法"的贡献来渲染。
 *
 * ★ 硬规则（总纲 §1.3.4）：一个贡献的 slot 必须出现在该插件 manifest.slots 里，
 *   多一个少一个都不许挂——这里在读取时强制过滤，越权贡献直接不渲染。
 * ★ 禁用即失效：贡献随插件在 store 中的 enabled 状态实时增删。
 *
 * 贡献登记是"外部可变源"，用 useSyncExternalStore 让消费者在登记/注销时实时重渲染。
 */

const registry = new Map<string, SlotContribution[]>();

let version = 0;
const listeners = new Set<() => void>();

function emit(): void {
  version += 1;
  for (const l of listeners) l();
}

function subscribe(cb: () => void): () => void {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
}

function getVersion(): number {
  return version;
}

/** 登记某插件的所有插槽贡献（覆盖式）。 */
export function registerContributions(pluginId: string, items: SlotContribution[]): void {
  registry.set(pluginId, items);
  emit();
}

/** 注销某插件的所有插槽贡献（卸载时调用）。 */
export function unregisterContributions(pluginId: string): void {
  registry.delete(pluginId);
  emit();
}

/**
 * 清空全部贡献登记（**仅测试隔离用**，产品代码不要调用）。
 *
 * `registry` 是模块级 Map，会**跨测试残留**：上一个测试登记的组件会继续参与渲染，
 * 表现为"本测试找不到自己的文本"，且不报任何错 —— 实测踩过一次：
 * 上一个测试那个"故意抛错"的组件盖住了本测试的组件，排查了很久。
 * 测试的 `beforeEach` 里调用它即可。
 */
export function clearContributions(): void {
  registry.clear();
  emit();
}

/** 取出某扩展点下、已启用且声明合法的贡献（非 Hook，可在测试/逻辑中直接调用）。 */
export function contributionsForSlot(
  slot: SlotName,
  modules?: Record<string, ModuleReg>,
): SlotContribution[] {
  const mods = modules ?? useDesktopStore.getState().modules;
  const out: SlotContribution[] = [];
  for (const [pluginId, items] of registry) {
    const reg = mods[pluginId];
    if (!reg || !reg.enabled) continue; // 禁用插件不贡献
    const declared = (reg.manifest.slots ?? []) as SlotName[];
    if (!declared.includes(slot)) continue; // 必须与 manifest.slots 一致
    for (const it of items) {
      if (it.slot === slot) out.push(it);
    }
  }
  return out.sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
}

/** 响应式版本：随贡献登记/注销与桌面 store 的启用态实时更新。 */
export function useSlotContributions(slot: SlotName): SlotContribution[] {
  // ★ version 必须接住并进 useMemo 的依赖，否则是个**静默失败**（实测踩过）：
  //   emit() 改了 version → useSyncExternalStore 确实触发了重渲染，
  //   但 useMemo 依赖 [slot, modules] 两个引用都没变 → 命中缓存返回旧的空数组，
  //   于是"插件贡献永远不出现"，且不报任何错。
  const version = useSyncExternalStore(subscribe, getVersion);
  const modules = useDesktopStore((s) => s.modules);
  return useMemo(() => contributionsForSlot(slot, modules), [slot, modules, version]);
}
