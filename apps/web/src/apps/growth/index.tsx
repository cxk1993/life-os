/**
 * 成长罗盘插件入口（T14 加载器按 manifest.entry = "@/apps/growth" 加载）。
 * 主人 ⑧⑪：习惯/人格/健康 一窗多页（容器型模块，照 system 样板）。
 */
import type { ComponentType } from "react";
import GrowthApp from "./GrowthApp";

const PluginModule = {
  manifestId: "growth",
  Component: GrowthApp as ComponentType,
  slots: {},
};

export default PluginModule;
export { GrowthApp };
