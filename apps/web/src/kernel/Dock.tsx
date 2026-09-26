import { pluginHost } from "./ModuleRegistry";
import { useDesktopStore } from "./store";

/**
 * 底部模块坞。列出已注册模块；点图标 → 开窗（singleton 重复点=聚焦）。
 * 模块有打开的窗口时，图标亮起小圆点；被禁用时置灰且不可点。
 *
 * ★ 主人 ⑤/⑫（2026-09-25）：**合并入口** —— 底端栏不再每个模块一个按钮：
 *   被合并的模块（见 DOCK_MERGE）不单独出按钮，统一由**容器模块**承载
 *   （点容器 → 窗口内多页/页签展示，这正是主人要的「一个按钮打开，窗口内分页」）。
 *   **fail-safe**：容器模块不存在或未启用时，**保留原按钮**（绝不因合并丢入口）。
 */

/** ★ 合并映射：子模块 id → 容器模块 id（③ 主人 ⑤⑫ 点名分组）。 */
const DOCK_MERGE: Record<string, string> = {
  // ⑫ 能力目录 / MCP / 推送 / 账户与鉴权 / **导出中心**（主人 09-25 追加）→ 系统容器
  catalog: "system",
  mcp: "system",
  push: "system",
  auth: "system",
  export: "system",
  // ★ 主人 09-25「多余的按钮不必留呐」+ MiMo 9959b94 把 query/plugins 并入系统窗 7 页。
  //   注意：Dock 渲染遍历 store 全部模块，**不看 manifest slots**——MiMo 4c8aace 摘
  //   desktop.dock 槽不产生隐藏效果；收口必须在 DOCK_MERGE 做（此处即真修法）。
  query: "system",
  plugins: "system",
  // ⑤ 复盘 / 笔记 / 文档 → 知识库容器（三合一）
  review: "knowledge",
  notes: "knowledge",
  docs: "knowledge",
  diary: "knowledge",
  // ⑪ 人格 / 健康 → 成长罗盘
  persona: "growth",
  health: "growth",
  // ★ 主人 2026-09-25 令「todo（待办）也该与日程表合并」· 总监令 10 §2：
  //   日程表 / 待办 → schedule 容器（两页合一）。Dock 显隐唯一杠杆=DOCK_MERGE
  //   （坑谱 #15：manifest.slots 不产生隐藏效果，MiMo 4c8aace 前车之鉴）。
  calendar: "schedule",
  todo: "schedule",
  // ★ 主人 2026-09-26 令「替换了吧，宁缺毋滥」：
  //   ai-chat（AI 对话）已由 pi-agent 接管 —— **必须在 DOCK_MERGE 收口**，
  //   因为 Dock 渲染遍历 store 全部模块、**从不读 manifest.slots**
  //   （坑谱 #15：摘 desktop.dock 槽永远无效）。fail-safe：pi-agent 未启用时自动保留原按钮。
  "ai-chat": "pi-agent",
  // ★ 主人 2026-09-26 追加令「AI 编排也收，并进 pi-agent 当一个 tab」：
  //   agents（AI 编排）归口到 pi-agent —— 底端栏 AI 类入口**收敛为一个**，
  //   点开 pi-agent 即见「对话 / 编排」两页签（容器 MultitabFrame 承载）。
  //   fail-safe：pi-agent 未启用时自动保留 agents 原按钮。
  agents: "pi-agent",
};

export function Dock() {
  const modules = useDesktopStore((s) => s.modules);
  const windows = useDesktopStore((s) => s.windows);
  const openIds = new Set(windows.map((w) => w.moduleId));

  /** 某容器是否可用（存在 + 启用）——不可用则不合并，保原按钮。 */
  const containerReady = (target: string) => Boolean(modules[target]?.enabled);

  /** 子模块是否已被容器「吸收」。 */
  const isMerged = (id: string) => {
    const target = DOCK_MERGE[id];
    return Boolean(target) && containerReady(target as string);
  };

  return (
    <div className="dock" role="toolbar" aria-label="模块坞">
      {Object.values(modules)
        .filter((reg) => !isMerged(reg.manifest.id))
        .map((reg) => {
          const m = reg.manifest;
          const open = openIds.has(m.id);
          // 该容器吸收了几个子模块（用于角标提示，让主人知道"合并入口"里有什么）
          const absorbed = Object.entries(DOCK_MERGE)
            .filter(([child, target]) => target === m.id && Boolean(modules[child]))
            .map(([child]) => child);
          const cls = [
            "dock__item",
            open ? "dock__item--open" : "",
            reg.enabled ? "" : "dock__item--disabled",
          ]
            .filter(Boolean)
            .join(" ");
          return (
            <button
              key={m.id}
              type="button"
              className={cls}
              aria-label={
                absorbed.length > 0
                  ? `${m.name}（含 ${absorbed.length} 个并入模块）`
                  : m.name
              }
              title={absorbed.length > 0 ? `含：${absorbed.join(" / ")}` : m.name}
              disabled={!reg.enabled}
              onClick={() => {
                if (reg.enabled) pluginHost.open(m.id);
              }}
            >
              {open ? <span className="dock__dot" aria-hidden="true" /> : null}
              <span className="dock__icon">{m.icon ?? m.name.slice(0, 1)}</span>
              <span className="dock__label">{m.name}</span>
              {absorbed.length > 0 ? (
                <span className="dock__merged-badge" aria-hidden="true">
                  +{absorbed.length}
                </span>
              ) : null}
            </button>
          );
        })}
    </div>
  );
}
