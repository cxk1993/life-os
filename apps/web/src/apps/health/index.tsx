/** 健康插件入口（T14 按 manifest.entry 加载）。 */
import type { ComponentType } from "react";
import HealthApp from "./HealthApp";
import "./health.css";

const PluginModule = {
  manifestId: "health",
  Component: HealthApp as ComponentType,
  slots: {},
};

export default PluginModule;
export { HealthApp };
