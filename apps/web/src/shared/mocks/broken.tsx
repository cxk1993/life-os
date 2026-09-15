import type { PluginModule } from "@/kernel/types";

/**
 * 故意在模块求值阶段抛异常的 mock（用于验证容错）。
 * 打开这个模块时，入口加载会失败 —— 只有这一扇窗显示占位，
 * 其它窗口与整个桌面保持正常，不白屏。内核由 WindowFrame 的错误边界兜底。
 */
throw new Error("模拟模块加载失败：入口在求值阶段抛异常（用于验证容错）");

// 下面这行永远不会执行，仅满足类型导出形态。
const plugin: PluginModule = { manifestId: "mod-broken", Component: () => null };
export default plugin;
