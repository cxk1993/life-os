/** 健康插件入口（T14 按 manifest.entry 加载）。 */
import type { ComponentType } from "react";
import HealthApp from "./HealthApp";
import DashboardCard from "./slots/DashboardCard";
import HealthTrend from "./slots/HealthTrend";
import RightDockCard from "./slots/RightDockCard";
import "./health.css";

const PluginModule = {
  manifestId: "health",
  Component: HealthApp as ComponentType,
  slots: {
    "dashboard.card": DashboardCard as ComponentType,
    // D1：健康窗侧栏也展示趋势（E5 双形态首演）。
    "window.sidecar": { component: HealthTrend as ComponentType, attachTo: "health" },
    "desktop.dock-right": RightDockCard as ComponentType,
  },
};

export default PluginModule;
export { HealthApp, DashboardCard, HealthTrend, RightDockCard };
