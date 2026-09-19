import { createContext, useContext } from "react";

/**
 * ★ T22：当前窗口的 `instanceId` 上下文。
 *
 * 用途：**窗口内的插件**需要操作"自己所在的那扇窗"时，从这里拿 id，
 * 而不是去猜 `moduleId` 反查（同一模块可能开了多扇窗，反查会拿错）。
 *
 * ★ 内核零业务：这里只有"一扇窗的 id"，不认识任何模块名。
 * ★ 与 `plugins/PluginContext.tsx` 分开成独立文件，是为了避免 eslint 的
 *   `react-refresh/only-export-components` 警告（同一文件既导出组件又导出 hook）。
 */
export const WindowInstanceContext = createContext<string | null>(null);

/** 取当前窗口的 instanceId；不在窗口内时返回 null。 */
export function useWindowInstance(): string | null {
  return useContext(WindowInstanceContext);
}
