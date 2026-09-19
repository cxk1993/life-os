/**
 * 文档插件入口（T14 加载器按 manifest.entry = "@apps/docs" 加载）。
 */
import type { ComponentType } from "react";
import DocsApp from "./DocsApp";
import "./docs.css";

const PluginModule = {
  manifestId: "docs",
  Component: DocsApp as ComponentType,
  slots: {},
};

export default PluginModule;
export { DocsApp };
export { DocsTree } from "./DocsTree";
export { DocsViewer } from "./DocsViewer";
export { MarkdownView } from "./MarkdownView";
