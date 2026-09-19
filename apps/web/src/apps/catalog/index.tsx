/**
 * 能力目录插件入口（T14 加载器按 manifest.entry = "@apps/catalog" 加载）。
 */
import type { ComponentType } from "react";
import CatalogApp from "./CatalogApp";
import "./catalog.css";

const PluginModule = {
  manifestId: "catalog",
  Component: CatalogApp as ComponentType,
  slots: {},
};

export default PluginModule;
export { CatalogApp };
