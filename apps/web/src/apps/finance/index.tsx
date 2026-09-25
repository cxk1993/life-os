/**
 * 理财插件入口（T14 加载器按 manifest.entry = "@apps/finance" 加载）。
 *
 * ★ 2026-09-25（astrbot · 主人令「下场」）：Component 改为 `FinanceTabbedApp`
 *   —— ⑨「理财=分页内嵌外部网页」形态落地（账本 iframe + 本地流水两页）。
 *   原 `FinanceApp` 未改动，仍导出（回退只需把 Component 改回它）。
 */
import type { ComponentType } from "react";
import FinanceTabbedApp from "./FinanceTabbedApp";
import FinanceApp from "./FinanceApp";
import "./finance.css";

const PluginModule = {
  manifestId: "finance",
  Component: FinanceTabbedApp as ComponentType,
  slots: {},
};

export default PluginModule;
export { FinanceApp, FinanceTabbedApp };
