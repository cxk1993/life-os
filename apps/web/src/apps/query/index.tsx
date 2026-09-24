/**
 * query 插件入口（manifest.entry = "@/apps/query"）。
 */
import type { ComponentType } from "react";
import QueryApp from "./QueryApp";
import "./query.css";

const PluginModule = {
  manifestId: "query",
  Component: QueryApp as ComponentType,
  slots: {},
};

export default PluginModule;
export { QueryApp };
