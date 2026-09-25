/**
 * 日程待办插件入口（T14 加载器按 manifest.entry = "@/apps/schedule" 加载）。
 *
 * ★ 2026-09-25（Qoder CN · 主人令「todo 与日程表合并」· 总监令 10）：
 *   Component = ScheduleApp（MultitabFrame 两页：日程表 / 待办）。
 *   原 `CalendarApp`/`TodoApp` 未改动（lazy 复用）；容器壳回退=改一行 Component。
 */
import type { ComponentType } from "react";
import ScheduleApp from "./ScheduleApp";

const PluginModule = {
  manifestId: "schedule",
  Component: ScheduleApp as ComponentType,
  slots: {},
};

export default PluginModule;
export { ScheduleApp };
