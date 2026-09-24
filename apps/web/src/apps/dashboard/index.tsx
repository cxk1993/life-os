/**
 * 成长罗盘插件入口（T14 加载器按 manifest.entry = "@apps/dashboard" 加载）。
 *
 * 本插件是 SlotHost 的**消费者**：其它插件的 dashboard.card 卡片在 DashboardApp
 * 里通过 <SlotHost slot="dashboard.card" /> 渲染；自己不往该扩展点挂卡片。
 */
import type { ComponentType } from "react";
import DashboardApp from "./DashboardApp";
import LandmarksSidecar from "./slots/LandmarksSidecar";
import "./dashboard.css";

const PluginModule = {
  manifestId: "dashboard",
  Component: DashboardApp as ComponentType,
  slots: {
    // C′ landmark 第二例：里程碑侧栏卡，只挂成长罗盘窗（attachTo: "dashboard"）。
    // 数据消费第三方 countdown 插件的 /landmarks（未安装时 404 → 卡自动不出现）。
    "window.sidecar": { component: LandmarksSidecar as ComponentType, attachTo: "dashboard" },
  },
};

export default PluginModule;
export { DashboardApp };
