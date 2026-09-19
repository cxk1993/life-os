/**
 * 日记插件入口（T14 加载器按 manifest.entry = "@apps/diary" 加载）。
 */
import type { ComponentType } from "react";
import DiaryApp from "./DiaryApp";
import "./diary.css";

const PluginModule = {
  manifestId: "diary",
  Component: DiaryApp as ComponentType,
  slots: {},
};

export default PluginModule;
export { DiaryApp };
