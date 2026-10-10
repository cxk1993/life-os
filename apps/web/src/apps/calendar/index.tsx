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
    // ★ 2026-09-27（主人「右栏更新」）：
    //   原先 calendar 与 diary 各挂一张几乎相同的迷你日历，右栏上下重复。
    //   现**合并为 diary 侧的一张四色融合日历**（day-dots + day-peek 打底），
    //   本卡不再注册 —— 组件文件保留（可单测），只是不再占右栏。
  },
};

export default PluginModule;

// 同时具名导出，便于测试 / 其他入口按需引用
export { CalendarApp, DashboardCard };
