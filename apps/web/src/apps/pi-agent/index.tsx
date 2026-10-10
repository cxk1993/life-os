/**
 * pi-agent 插件入口（★ manifest.entry = "@/apps/pi-agent"）。
 *
 * ★ 为什么 UI 放在 `src/apps/`（而非 plugins/pi-agent/web/）：
 *   前端内核的 `ModuleRegistry.resolveLoader` **只认 `src/apps/<dir>/index.tsx`**
 *（`import.meta.glob` 构建期发现，见 ModuleRegistry.ts 顶部注释）。这是内核的
 *   既定约定——"加新插件 = 多一个目录 + manifest 登记 entry，不必改内核"。
 *   后端 kind 仍是 `third-party`（**可禁用、可卸载**），UI 只是按约定落在扫描目录里。
 */
import type { ComponentType } from "react";

import PiAgentApp from "./PiAgentApp";
import PiChatView from "./PiChatView";
import "./pi-agent.css";

const PluginModule = {
  manifestId: "pi-agent",
  Component: PiAgentApp as ComponentType,
  slots: {},
};

export default PluginModule;
export { PiAgentApp, PiChatView };
