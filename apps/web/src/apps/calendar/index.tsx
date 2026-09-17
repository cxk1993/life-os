/**
 * 日程表插件入口（T14 加载器按 manifest.entry = "@apps/calendar" 加载）。
 * 默认导出 PluginModule：包含 manifestId、主组件、以及 dashboard 卡片插槽。
 */

import type { ComponentType } from "react";
import { CalendarApp } from "./CalendarApp";
import { DashboardCard } from "./slots/DashboardCard";

const PluginModule = {
  manifestId: "calendar",
  Component: CalendarApp as ComponentType,
  slots: {
    "dashboard.card": DashboardCard as ComponentType,
  },
};

export default PluginModule;

// 同时具名导出，便于测试 / 其他入口按需引用
export { CalendarApp, DashboardCard };
