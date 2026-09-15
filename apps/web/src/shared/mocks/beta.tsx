import type { PluginModule } from "@/kernel/types";

function BetaApp() {
  return (
    <div className="mock-app">
      <h2>演示模块 · 乙</h2>
      <p>另一个占位窗口。打开它并和「甲」并排，可以验证聚焦置顶与 z-index 递增。</p>
      <span className="mock-app__tag">mock · beta</span>
    </div>
  );
}

const plugin: PluginModule = {
  manifestId: "mod-beta",
  Component: BetaApp,
};

export default plugin;
