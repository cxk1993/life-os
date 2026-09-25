/**
 * plugins 插件管理入口（并入系统窗多页时由 SystemApp lazy 加载）。
 */
import type { ComponentType } from "react";
import PluginsApp from "./PluginsApp";
import "./plugins.css";

const PluginModule = {
  manifestId: "plugins",
  Component: PluginsApp as ComponentType,
  slots: {},
};

export default PluginModule;
export { PluginsApp };
