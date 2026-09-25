/**
 * sidebar 插件入口（manifest.entry = "@/apps/sidebar"）。
 */
import type { ComponentType } from "react";
import SidebarApp from "./SidebarApp";
import "./sidebar.css";

const PluginModule = {
  manifestId: "sidebar",
  Component: SidebarApp as ComponentType,
  slots: {},
};

export default PluginModule;
export { SidebarApp };
