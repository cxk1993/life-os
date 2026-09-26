/**
 * ★ Pi 智能体 · 一窗多页容器（主人 2026-09-26 令：「AI 编排也收，并进 pi-agent 当一个 tab」）。
 *
 * 结构（照 `apps/schedule/ScheduleApp.tsx` 容器样板 · kernel/MultitabFrame 原语）：
 *   页 1「对话」= PiChatView（TX-FRAME-01 第⑤刀原件，**一字未改**）
 *   页 2「编排」= AgentsApp（AI 编排原件，**一字未改**，lazy 引用）
 *
 * ★ 为什么这样并：Dock 显隐唯一杠杆是 DOCK_MERGE（坑谱 #15），
 *   `agents` 与 `ai-chat` 均已在 DOCK_MERGE 归口到 pi-agent —— 于是
 *   底端栏只剩**一个** AI 入口，点开即是「对话 / 编排」两页签。
 *   fail-safe：pi-agent 未启用时，Dock 自动保留原子模块按钮（绝不丢入口）。
 *
 * ★ 跨插件 import 说明：ADR-0002 禁的是「插件互相 import 逻辑」；
 *   本处是**容器模块按内核约定 lazy 引用子模块的视图 App**（与 schedule/growth/
 *   knowledge/system 四个既有容器同构，属官方样板用法，非新增例外）。
 */
import { lazy, Suspense } from "react";
import MultitabFrame from "@/kernel/MultitabFrame";

const PiChatView = lazy(() => import("./PiChatView"));
// AgentsApp 是 default 导出，直引即可。原 App 一字未改。
const AgentsApp = lazy(() => import("../agents/AgentsApp"));

function PageFallback() {
  return <div className="dash-muted" data-testid="pi-agent-loading">加载中…</div>;
}

const wrap = (node: React.ReactNode) => (
  <Suspense fallback={<PageFallback />}>{node}</Suspense>
);

export default function PiAgentApp() {
  return (
    <div className="pi-agent-win" style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <MultitabFrame
        ariaLabel="Pi 智能体"
        persistKey="pi-agent-win"
        pages={[
          { key: "chat", label: "对话", content: wrap(<PiChatView />) },
          { key: "agents", label: "编排", content: wrap(<AgentsApp />) },
        ]}
      />
    </div>
  );
}
