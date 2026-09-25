import { describe, expect, it } from "vitest";

import { manifestToModule } from "./PluginRegistry";
import type { PluginInfo } from "./types";

/**
 * ★ 根因 E 回归（2026-09-25 · hermes 亲修 · 主人真机报「plugins 清单缺少 entry 字段」）：
 *   后端同步的 core/builtin 插件（无 UI，仅 API）manifest 里带 api 字段，
 *   manifestToModule 必须**透传 api** —— WindowFrame 靠 `manifest.api.base`
 *   区分「已接入（后端服务）」与「该模块尚未接入」。丢了 api 就是把健康的
 *   后端模块误报成未接入（⑬ 同款病，换了触发路径）。
 */
describe("manifestToModule · api 透传（根因 E）", () => {
  it("带 api 的插件：转换后 manifest.api 原样保留", () => {
    const p = {
      id: "plugins",
      name: "插件管理",
      version: "0.1.0",
      kind: "core",
      enabled: true,
      source: "core",
      manifest: {
        id: "plugins",
        name: "插件管理",
        version: "0.1.0",
        kind: "core",
        entry: "",
        window: { w: 640, h: 420 },
        slots: [],
        api: { base: "/api/v1/plugins", health: "/api/v1/plugins/health" },
      },
    } as unknown as PluginInfo;
    const mod = manifestToModule(p);
    expect(
      (mod as { api?: { base?: string } }).api?.base,
    ).toBe("/api/v1/plugins");
  });

  it("缺 manifest 的幽灵项：api 为 undefined，不抛错（ISSUE-012 防御保持）", () => {
    const ghost = {
      id: "ghost",
      name: "幽灵",
      version: "0.1.0",
      kind: "builtin",
      enabled: true,
      source: "builtin",
    } as unknown as PluginInfo;
    expect(() => manifestToModule(ghost)).not.toThrow();
    expect((manifestToModule(ghost) as { api?: unknown }).api).toBeUndefined();
  });
});
