/**
 * 复盘插件入口（T14 加载器按 manifest.entry = "@apps/review" 加载）。
 */
import type { ComponentType } from "react";
import ReviewApp from "./ReviewApp";
import "./review.css";

const PluginModule = {
  manifestId: "review",
  Component: ReviewApp as ComponentType,
  slots: {},
};

export default PluginModule;
export { ReviewApp };
