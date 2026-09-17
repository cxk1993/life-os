/**
 * 理财插件入口（T14 加载器按 manifest.entry = "@apps/finance" 加载）。
 */
import type { ComponentType } from "react";
import FinanceApp from "./FinanceApp";
import "./finance.css";

const PluginModule = {
  manifestId: "finance",
  Component: FinanceApp as ComponentType,
  slots: {},
};

export default PluginModule;
export { FinanceApp };
