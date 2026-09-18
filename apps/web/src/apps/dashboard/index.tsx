/**
 * 成长罗盘插件入口（T14 加载器按 manifest.entry = "@apps/dashboard" 加载）。
 *
 * 本插件是 SlotHost 的**消费者**：其它插件的 dashboard.card 卡片在 DashboardApp
 * 里通过 <SlotHost slot="dashboard.card" /> 渲染；自己不往该扩展点挂卡片。
 */
import type { ComponentType } from "react";
import DashboardApp from "./DashboardApp";
import "./dashboard.css";

const PluginModule = {
  manifestId: "dashboard",
  Component: DashboardApp as ComponentType,
  slots: {},
};

export default PluginModule;
export { DashboardApp };
