import type { PluginModule } from "@/kernel/types";

/**
 * 演示模块 · 甲（mock）。仅用于验证窗口系统的「开窗 / 拖 / 缩放 / 聚焦 / 关闭」。
 * 不是任何真实业务插件；内核不依赖它。入口抛错的情况见 broken.tsx。
 */
function AlphaApp() {
  return (
    <div className="mock-app">
      <h2>演示模块 · 甲</h2>
      <p>
        这是用于验收多开窗口系统的占位模块。你可以拖动标题栏、拉八向手柄缩放、
        双击标题栏最大化、点标题栏右侧按钮最小化或关闭，也可以连续开多扇窗体验聚焦置顶。
      </p>
      <span className="mock-app__tag">mock · alpha</span>
    </div>
  );
}

const plugin: PluginModule = {
  manifestId: "mod-alpha",
  Component: AlphaApp,
};

export default plugin;
