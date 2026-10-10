/**
 * 成长罗盘 · V6 容器化（主人⑧⑪：习惯/人格/健康并入罗盘多页展示）。
 *
 * 原 24 行占位组件替换为 MultitabFrame 三页容器（指路帖 §1 页签源）：
 * - 页视图源 = 现有模块 App 组件直接复用，不重写；
 * - React.lazy 动态 import 保持模块懒加载分包（不把三模块打进 dashboard chunk）；
 * - growth prop 保留（DashboardApp 调用签名不变；overview.growth 数据源仍是
 *   GET /api/v1/dashboard/growth 占位端点，V6 二期后端三轴就绪后回填展示）。
 */
import { lazy, Suspense } from "react";
import MultitabFrame from "@/kernel/MultitabFrame";
import type { GrowthBlock } from "./api";

const HabitsApp = lazy(() => import("../habits/HabitsApp"));
const PersonaApp = lazy(() =>
  import("../persona/PersonaApp").then((m) => ({ default: m.PersonaApp })),
);
const HealthApp = lazy(() => import("../health/HealthApp"));

function PageFallback() {
  return <div className="dash-muted" data-testid="growth-page-loading">加载中…</div>;
}

export default function GrowthPanel({ growth }: { growth: GrowthBlock }) {
  // growth 数据暂存 prop（三轴后端未就绪，占位端点形状见 api.ts）——
  // 容器化不阻塞，后端回填时在此接入总览页。
  void growth;

  return (
    <section className="dash-card dash-card--flush" aria-label="成长罗盘">
      <div className="dash-card__title">成长罗盘</div>
      <MultitabFrame
        ariaLabel="成长罗盘页签"
        persistKey="growth"
        pages={[
          { key: "habits", label: "习惯", content: <Suspense fallback={<PageFallback />}><HabitsApp /></Suspense> },
          { key: "persona", label: "人格体系", content: <Suspense fallback={<PageFallback />}><PersonaApp /></Suspense> },
          { key: "health", label: "健康", content: <Suspense fallback={<PageFallback />}><HealthApp /></Suspense> },
        ]}
      />
    </section>
  );
}
