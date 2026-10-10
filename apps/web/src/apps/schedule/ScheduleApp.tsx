/**
 * ★ 日程待办 · **三页**合一窗口（2026-09-26 加「学业」页 · 主人：
 *   「大学的课很多很杂…与正常待办混在一起非常乱 → 分一个专门的学业页」）。
 *
 * ★ 原两页合一窗口（主人 2026-09-25 令：
 *   「todo（待办）是不是也应该与日程表合并？采用一个窗口多个分页展示的形式」
 *   · 派 Qoder CN 施工，批 J 件）。
 *
 * 实现（Qoder CN · 照 knowledge/growth/system 容器样板）：
 *   复用 `kernel/MultitabFrame`，两页 = 日程表 / 待办；
 *   页视图源**直接复用现有模块 App**（懒加载，两个原 App 一字未改）。
 *
 * 判据（四枚）：①原 calendar/todo manifest/路由/API 一字不动 ✅
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
// ★ 2026-09-26（astrbot · 主人「学业页」）：第三页 —— 学业专页
//（作业清单，按 deadline 升序；数据源 = todoApi.list({tag:"学业"})，复用后端层级标签）
const StudyApp = lazy(() => import("../study/StudyApp"));
// ★ 2026-09-27（hermes · 主人「日程待办里加一页课程表」）：第四页 —— 课程表
//（周网格：课名/教师/地点/节次/周次；数据源 = /api/v1/course/week）
const CourseApp = lazy(() => import("../course/CourseApp"));

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
          { key: "study", label: "学业", content: wrap(<StudyApp />) },
          { key: "course", label: "课程表", content: wrap(<CourseApp />) },
        ]}
      />
    </div>
  );
}
