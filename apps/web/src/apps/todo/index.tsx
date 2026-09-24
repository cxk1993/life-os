/**
 * 待办插件入口（T14 加载器按 manifest.entry = "@apps/todo" 加载）。
 */
import type { ComponentType } from "react";
import TodoApp from "./TodoApp";
import DashboardCard from "./slots/DashboardCard";
import DockCard from "./slots/DockCard";
import SidecarSummary from "./slots/SidecarSummary";
import "./todo.css";

const PluginModule = {
  manifestId: "todo",
  Component: TodoApp as ComponentType,
  slots: {
    "dashboard.card": DashboardCard as ComponentType,
    // E5 首例：窗口侧栏卡片，只挂在日程表窗（attachTo: "calendar"）。
    "window.sidecar": { component: SidecarSummary as ComponentType, attachTo: "calendar" },
    // U3 首例：桌面右栏 dock 卡（dock 数据规范 v1：消费 /today-summary 三态）。
    "desktop.dock-right": DockCard as ComponentType,
  },
};

export default PluginModule;
export { TodoApp, DashboardCard, DockCard, SidecarSummary };
