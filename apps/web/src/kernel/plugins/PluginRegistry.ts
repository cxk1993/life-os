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
    // ISSUE-012 防御：manifest 缺失时给安全默认值（空 entry / 兜底窗口 / 空 slots），
    // 使模块仍可注册（Dock 可见）但无任何 UI 贡献，绝不抛错。
    entry: p.manifest?.entry ?? "",
    window: p.manifest?.window ?? { ...FALLBACK_WINDOW },
    // ★ 根因 E 修复（2026-09-25 · 总监令 · 主人真机报「plugins 模块清单缺少 entry 字段」）：
    //   必须透传 api —— WindowFrame 用 `manifest.api.base` 判定「后端模块（合法无 UI）」
    //   与「真缺失」。此前三容器（system/knowledge/growth）走 modules.json 静态注册带着
    //   api 才显示正常；而后端同步的 core/builtin 插件（plugins/summary/query/export/auth）
    //   丢了 api → 明明有 API 却被判「该模块尚未接入 · 清单缺少 entry 字段」。
    api: (p.manifest as { api?: Record<string, unknown> } | undefined)?.api,
    slots: p.manifest?.slots ?? [],
  };
}

/**
 * 把后端插件清单同步进桌面模块注册表，并按启用态开/关。
 *
 * ISSUE-012 防御：后端 `list_plugins()` 曾漏掉 `manifest` 字段（已由令55 修），
 * 契约测试断言前，前端先做到「manifest 缺失不崩」——
 * 无 manifest 项跳过（记 warning，不进 store），其余项照常注册。
 */
export function syncPluginsToStore(plugins: PluginInfo[]): void {
  for (const p of plugins) {
    if (!p.manifest) {
      // ★ 数据异常保护：缺 manifest 的项不能进 store（Dock 会渲染出无入口的幽灵模块），
      // 也绝不能让它把整个同步循环打断（历史上它会让贡献注册整体挂不上）。
      console.warn(
        `[plugins] 插件「${p.id}」缺少 manifest，已跳过同步（后端契约应保证该字段存在）`,
      );
      continue;
    }
    pluginHost.register(manifestToModule(p));
    if (p.enabled) {
      pluginHost.enable(p.id);
    } else {
      pluginHost.disable(p.id);
    }
  }
}
