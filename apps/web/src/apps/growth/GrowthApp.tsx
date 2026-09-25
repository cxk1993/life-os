/**
 * ★ 成长罗盘 · 独立窗口（主人 ⑧⑪：「合并到**成长罗盘的窗口展示页**里面去，多页化展示」）
 *
 * 实现（astrbot 下场 · 2026-09-25）：
 *   复用 `kernel/MultitabFrame`，三页 = 习惯 / 人格体系 / 健康。
 *   页视图源**直接复用现有模块 App**（懒加载，不重写业务、不把三模块打进本 chunk）。
 *
 * 与 `dashboard/GrowthPanel.tsx` 的关系：
 *   那个是 dashboard 里的**卡片**（保留不动）；本组件是**独立窗口**版本。
 *   两者共用同一套"三页"结构，`persistKey` 用不同键（`growth-win`）以免互相干扰。
 */
import { lazy, Suspense } from "react";
import MultitabFrame from "@/kernel/MultitabFrame";

const HabitsApp = lazy(() => import("../habits/HabitsApp"));
const PersonaApp = lazy(() =>
  import("../persona/PersonaApp").then((m) => ({ default: m.PersonaApp })),
);
const HealthApp = lazy(() => import("../health/HealthApp"));

function PageFallback() {
  return <div className="dash-muted" data-testid="growth-win-loading">加载中…</div>;
}

const wrap = (node: React.ReactNode) => (
  <Suspense fallback={<PageFallback />}>{node}</Suspense>
);

export default function GrowthApp() {
  return (
    <div className="growth-win" style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <MultitabFrame
        ariaLabel="成长罗盘"
        persistKey="growth-win"
        pages={[
          { key: "habits", label: "习惯", content: wrap(<HabitsApp />) },
          { key: "persona", label: "人格体系", content: wrap(<PersonaApp />) },
          { key: "health", label: "健康", content: wrap(<HealthApp />) },
        ]}
      />
    </div>
  );
}
