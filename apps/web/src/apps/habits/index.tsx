/**
 * 习惯打卡插件入口（T14 加载器按 manifest.entry = "@apps/habits" 加载）。
 */
import type { ComponentType } from "react";
import HabitsApp from "./HabitsApp";
import DashboardCard from "./slots/DashboardCard";
import "./habits.css";

const PluginModule = {
  manifestId: "habits",
  Component: HabitsApp as ComponentType,
  slots: {
    "dashboard.card": DashboardCard as ComponentType,
  },
};

export default PluginModule;
export { HabitsApp, DashboardCard };
