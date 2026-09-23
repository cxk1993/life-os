/**
 * 推送插件入口（T14 加载器按 manifest.entry = "@apps/push" 加载）。
 *
 * ★ slots 必须与后端 `modules/push/manifest.json` 的 `slots` 一字不差
 *   （总纲 §1.3.4 硬规则）——多了少了都会被 contributionsForSlot 静默过滤。
 */
import type { ComponentType } from "react";

import PushApp from "./PushApp";
import DockBadge from "./slots/DockBadge";
import SettingsPage from "./slots/SettingsPage";
import "./push.css";

const PluginModule = {
  manifestId: "push",
  Component: PushApp as ComponentType,
  slots: {
    "desktop.dock": DockBadge as ComponentType,
    "settings.page": SettingsPage as ComponentType,
  },
};

export default PluginModule;

// 具名导出，便于测试与其他入口按需引用
export { PushApp, DockBadge, SettingsPage };
