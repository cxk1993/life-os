/**
 * ★ 日程待办 · 两页合一窗口（主人 2026-09-25 令：
 *   「todo（待办）是不是也应该与日程表合并？采用一个窗口多个分页展示的形式」
 *   · 总监令 10 §2 派 Qoder CN 施工，批 J 件）。
 *
 * 实现（Qoder CN · 照 knowledge/growth/system 容器样板）：
 *   复用 `kernel/MultitabFrame`，两页 = 日程表 / 待办；
 *   页视图源**直接复用现有模块 App**（懒加载，两个原 App 一字未改）。
 *
 * 判据（总监令10 §2 四枚）：①原 calendar/todo manifest/路由/API 一字不动 ✅
 * ②Dock 收口走 DOCK_MERGE（kernel/Dock.tsx · 坑谱 #15 的 DOCK_MERGE 真修法）✅
 * ③待办到期提醒（todo/due_scheduler·ec41c51）与本容器无耦合 ✅（不碰其代码）
 * ④容器 test + kernel 全量 + tsc 0。
 */
import { lazy, Suspense } from "react";
import MultitabFrame from "@/kernel/MultitabFrame";

// CalendarApp 是命名导出（无 default）——lazy 需要 default，故 .then 适配一层；
// TodoApp 是 default导出，直引即可。原 App 一字未改。
const CalendarApp = lazy(() =>
  import("../calendar/CalendarApp").then((m) => ({ default: m.CalendarApp })),
);
const TodoApp = lazy(() => import("../todo/TodoApp"));

function PageFallback() {
  return <div className="dash-muted" data-testid="schedule-loading">加载中…</div>;
}

const wrap = (node: React.ReactNode) => (
  <Suspense fallback={<PageFallback />}>{node}</Suspense>
);

export default function ScheduleApp() {
  return (
    <div className="schedule-win" style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <MultitabFrame
        ariaLabel="日程待办"
        persistKey="schedule-win"
        pages={[
          { key: "calendar", label: "日程表", content: wrap(<CalendarApp />) },
          { key: "todo", label: "待办", content: wrap(<TodoApp />) },
        ]}
      />
    </div>
  );
}
