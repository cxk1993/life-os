import type { SlotName } from "../plugins/types";

/**
 * 13 个扩展点（总纲 §1.3.4）。扩展点是内核资产：第三方插件只能往这里挂东西，
 * 不得新增扩展点（需要新扩展点走 RFC——E5 起新增 13 号 `window.sidecar`）。
 *
 * 这一层只定义"有哪些扩展点、各自挂在哪个区域、叫什么"，不渲染任何业务内容——
 * 渲染交给 SlotHost + 各插件的贡献组件。
 */
export interface SlotMeta {
  name: SlotName;
  title: string;
  description: string;
  /** 该扩展点的挂载体（DOM 区域），仅用于文档与校验。 */
  mount: string;
}

export const SLOTS: Record<SlotName, SlotMeta> = {
  "desktop.dock": {
    name: "desktop.dock",
    title: "桌面坞",
    description: "桌面底部模块坞，可挂常驻快捷入口",
    mount: "桌面坞",
  },
  "desktop.widget": {
    name: "desktop.widget",
    title: "桌面小组件",
    description: "桌面背景层小组件",
    mount: "桌面小组件层",
  },
  "dashboard.card": {
    name: "dashboard.card",
    title: "概览卡片",
    description: "概览/仪表盘页卡片",
    mount: "概览页",
  },
  "topbar.action": {
    name: "topbar.action",
    title: "顶栏动作",
    description: "顶栏右侧动作区",
    mount: "顶栏",
  },
  "calendar.block.renderer": {
    name: "calendar.block.renderer",
    title: "日程块渲染",
    description: "自定义日程块渲染",
    mount: "日程",
  },
  "calendar.overlay": {
    name: "calendar.overlay",
    title: "日程浮层",
    description: "日程层浮层",
    mount: "日程",
  },
  "inspector.panel": {
    name: "inspector.panel",
    title: "检视面板",
    description: "侧边 inspector 面板",
    mount: "检视面板",
  },
  "settings.page": {
    name: "settings.page",
    title: "设置分页",
    description: "设置页分页",
    mount: "设置页",
  },
  "search.provider": {
    name: "search.provider",
    title: "搜索来源",
    description: "全局搜索结果来源",
    mount: "全局搜索",
  },
  "ai.tool": {
    name: "ai.tool",
    title: "AI 工具",
    description: "AI 可调用的工具",
    mount: "AI",
  },
  "notification.channel": {
    name: "notification.channel",
    title: "通知通道",
    description: "通知通道",
    mount: "通知",
  },
  "command.palette": {
    name: "command.palette",
    title: "命令面板",
    description: "命令面板条目",
    mount: "命令面板",
  },
  "window.sidecar": {
    name: "window.sidecar",
    title: "窗口侧栏卡片",
    description: "窗口内寄生小面板（attachTo 指定目标窗口，缺省全窗）",
    mount: "窗口侧栏",
  },
  // U3（桌面级）：E5 window.sidecar 的桌面级兄弟——同一机制，两级挂载点。
  "desktop.dock-left": {
    name: "desktop.dock-left",
    title: "桌面左侧栏",
    description: "桌面级左侧栏（左=导航/结构惯例）；折叠持久化、tooltip、aria-expanded",
    mount: "桌面左侧栏",
  },
  "desktop.dock-right": {
    name: "desktop.dock-right",
    title: "桌面右侧栏",
    description: "桌面级右侧栏（右=摘要/情境惯例：今日摘要、待办、健康趋势）",
    mount: "桌面右侧栏",
  },
};

export const SLOT_NAMES = Object.keys(SLOTS) as SlotName[];

export function isSlotName(value: string): value is SlotName {
  return Object.prototype.hasOwnProperty.call(SLOTS, value);
}
