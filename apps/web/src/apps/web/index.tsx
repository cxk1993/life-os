/**
 * 网页工作台插件入口（T14 的加载器按 manifest.entry = "@apps/web" 加载它）。
 * ★ 插件形态与 todo 一致：default 导出 { manifestId, Component, slots? }。
 */
import type { ComponentType } from "react";
import WebApp from "./WebApp";
import "./web.css";

const PluginModule = {
  manifestId: "web",
  Component: WebApp as ComponentType,
};

export default PluginModule;
export { WebApp };
