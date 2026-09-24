/**
 * export 插件入口（manifest.entry = "@/apps/export"）。
 */
import type { ComponentType } from "react";
import ExportApp from "./ExportApp";
import "./export.css";

const PluginModule = {
  manifestId: "export",
  Component: ExportApp as ComponentType,
  slots: {},
};

export default PluginModule;
export { ExportApp };
