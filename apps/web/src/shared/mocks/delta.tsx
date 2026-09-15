import type { PluginModule } from "@/kernel/types";

/**
 * 演示模块 · 丁（mock）。清单里声明 singleton: true，
 * 用于验证「重复点击坞图标 = 聚焦已开窗，不重复开窗」。
 */
function DeltaApp() {
  return (
    <div className="mock-app">
      <h2>演示模块 · 丁（单例）</h2>
      <p>
        这个模块在 manifest 里是 singleton。重复点击坞图标不会开第二扇，只会把已有的这扇提到最前。
      </p>
      <span className="mock-app__tag">mock · delta · singleton</span>
    </div>
  );
}

const plugin: PluginModule = {
  manifestId: "mod-delta",
  Component: DeltaApp,
};

export default plugin;
