import type { ComponentType } from "react";

/**
 * 模块清单类型（对齐总纲 §1.3 manifest.json 字段表）。
 * 内核只认「一个模块」，绝不出现任何业务词汇。
 *
 * 说明：总纲 manifest 字段很多（provides/requires/slots/emits…），
 * 前端内核只用到下面这些；其余字段通过索引签名放行，不丢弃。
 */

export type ModuleKind = "core" | "builtin" | "third-party";

export interface ModuleWindowSpec {
  w: number;
  h: number;
  minW?: number;
  minH?: number;
  /** singleton: true 的模块重复点击 = 聚焦，不重复开窗。 */
  singleton?: boolean;
  /** 默认位置（可选，不填则级联排布）。 */
  x?: number;
  y?: number;
}

export interface ModuleManifest {
  id: string;
  name: string;
  version: string;
  kind: ModuleKind;
  icon?: string;
  description?: string;
  /** 动态 import 说明符，由内核 React.lazy 加载。 */
  entry: string;
  window: ModuleWindowSpec;
  // 允许其余契约字段（provides/requires/slots/emits/permissions…）原样透传
  [key: string]: unknown;
}

/**
 * 模块入口默认导出的形状（与总纲插件协议一致）。
 * 内核用 React.lazy 加载，取其 Component 渲染到窗口内。
 *
 * slots 支持两种形态（E5 起）：
 *   - 简写：`"dashboard.card": DashboardCard`（等价于 { component }）
 *   - 规格：`"window.sidecar": { component: SidecarSummary, attachTo: "calendar" }`
 *     attachTo = 附着目标窗口 moduleId；缺省 = 所有窗口。
 */
export interface SlotContributionSpec {
  component: ComponentType;
  /** E5：sidecar 附着目标窗口 moduleId；缺省 = 所有窗口渲染。 */
  attachTo?: string;
}

export interface PluginModule {
  manifestId: string;
  Component: ComponentType;
  slots?: Record<string, ComponentType | SlotContributionSpec>;
}
