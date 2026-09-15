import type { PluginModule } from "@/kernel/types";

function GammaApp() {
  return (
    <div className="mock-app">
      <h2>演示模块 · 丙</h2>
      <p>占位窗口三。把它的几何拖到某个位置并刷新页面，应当能恢复原位（localStorage 持久化）。</p>
      <span className="mock-app__tag">mock · gamma</span>
    </div>
  );
}

const plugin: PluginModule = {
  manifestId: "mod-gamma",
  Component: GammaApp,
};

export default plugin;
