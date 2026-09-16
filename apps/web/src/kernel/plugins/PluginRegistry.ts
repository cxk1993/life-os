import { pluginHost } from "../ModuleRegistry";
import type { ModuleManifest } from "../types";
import type { PluginInfo } from "./types";

/**
 * 前端插件注册表（T14 · 内核侧）。
 *
 * 职责：把后端 /api/v1/plugins 返回的插件清单同步进桌面 store，
 * 使"装了什么 / 启没启"对内核一视同仁——Dock/TopBar 直接读 store.modules，
 * 不认识任何具体插件。禁用即把 store 里该模块 enabled 置 false（Dock 自动置灰），
 * 启用即恢复。这与 T02 既有的 ModuleRegistry/store 接口完全对接，不改内核一行业务代码。
 */

const FALLBACK_WINDOW = { w: 640, h: 420 } as const;

export function manifestToModule(p: PluginInfo): ModuleManifest {
  return {
    id: p.id,
    name: p.name,
    version: p.version,
    kind: p.kind,
    icon: p.icon,
    description: p.description,
    entry: p.manifest.entry ?? "",
    window: p.manifest.window ?? { ...FALLBACK_WINDOW },
    // ★ 必须带上 slots —— 漏掉它会静默失败，是实测踩过的坑：
    //   contributionsForSlot() 的守卫要求「store 里 manifest.slots 包含该扩展点」，
    //   缺了 slots 时贡献会被**静默过滤**：插件装上了、启用了、也不报错，
    //   但界面就是不出现，查起来极费时间。
    slots: p.manifest.slots ?? [],
  };
}

/** 把后端插件清单同步进桌面模块注册表，并按启用态开/关。 */
export function syncPluginsToStore(plugins: PluginInfo[]): void {
  for (const p of plugins) {
    pluginHost.register(manifestToModule(p));
    if (p.enabled) {
      pluginHost.enable(p.id);
    } else {
      pluginHost.disable(p.id);
    }
  }
}
