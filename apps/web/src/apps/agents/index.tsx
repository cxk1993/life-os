/**
 * AI 编排插件入口（T14 加载器按 manifest.entry = "@apps/agents" 加载）。
 */
import type { ComponentType } from "react";
import AgentsApp from "./AgentsApp";
import DashboardCard from "./slots/DashboardCard";
import "./agents.css";

const PluginModule = {
  manifestId: "agents",
  Component: AgentsApp as ComponentType,
  slots: {
    "dashboard.card": DashboardCard as ComponentType,
  },
};

export default PluginModule;
export { AgentsApp, DashboardCard };
