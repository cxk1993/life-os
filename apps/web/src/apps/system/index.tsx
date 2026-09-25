/**
 * 系统窗插件入口（T14 加载器按 manifest.entry = "@/apps/system" 加载）。
 * V6：主人⑫ 四合一（能力目录/MCP/推送/账户与鉴权）编排模块。
 */
import type { ComponentType } from "react";
import SystemApp from "./SystemApp";

const PluginModule = {
  manifestId: "system",
  Component: SystemApp as ComponentType,
  slots: {},
};

export default PluginModule;
export { SystemApp };
