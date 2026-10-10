/**
 * ★ 学业专页（astrbot 2026-09-26 · 主人「学业页」）
 *
 * 需求：大学的课多且杂，每节课有自己的作业与 deadline，与日常待办混在一起很乱
 *       → 分一个**专门的学业页**：**作业清单，按 deadline 排序，最急的在最上**。
 *
 * 设计：
 *   - 数据源：`todoApi.list({ status: "todo", tag: "学业" })` —— 复用**后端层级标签**
 *（tag=学业 命中 `学业` 与 `学业/高数`、`学业/大物` …，见 todo/service.py tag_hit）；
 *   - 排序：`due_at` 升序（最急最上）；无 due_at 的置底；
 *   - 分组：**进行中**（有 deadline）/ **未排期**（无 deadline）/ **已完成**（折叠）；
 *   - 课程标签：取标签里 `学业/xxx` 的第二段显示为课程徽标（如「高数」）。
 *
 * 入口：schedule 容器的第 3 页（[日程表][待办][学业]）—— 与「待办」页里的"只看学业"
 *       筛选器形成**一轻一重**双入口（主人 2026-09-26 拍板）。
 */
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { EmptyState } from "@/shared/components/EmptyState";
import { Skeleton } from "@/shared/components/Skeleton";

import ErrorState from "../todo/ErrorState";
import ItemRow from "../todo/ItemRow";
import { todoApi } from "../todo/api";
import type { TodoItem } from "../todo/api";
import { isArchived } from "../todo/archive";
import { ARCHIVE_AFTER_DAYS } from "../todo/constants";
import "../todo/todo.css";
import { TODO_KEY_ROOT } from "../todo/keys";
import "./study.css";

const STUDY_TAG = "学业";

/** 从标签里取出课程名（`学业/高数` → `高数`）。 */
function courseOf(item: TodoItem): string | null {
  for (const t of item.tags ?? []) {
    if (t.startsWith(STUDY_TAG + "/")) {
      return t.slice(STUDY_TAG.length + 1);
    }
  }
  return null;
}

/** 剩余时间徽标文案 + 紧急度。 */
function dueBadge(due: string | null): { text: string; level: "over" | "soon" | "normal" } | null {
  if (!due) return null;
  const t = new Date(due).getTime();
  if (Number.isNaN(t)) return null;
  const diffMs = t - Date.now();
  const days = Math.floor(diffMs / 86_400_000);
  const hours = Math.floor(diffMs / 3_600_000);
  if (diffMs < 0) return { text: "已过期", level: "over" };
  if (hours < 24) return { text: `剩 ${Math.max(1, hours)} 小时`, level: "soon" };
  return { text: `剩 ${days} 天`, level: days <= 3 ? "soon" : "normal" };
}

export default function StudyApp() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: [TODO_KEY_ROOT, "study", "list"],
    // ★ tag=学业 → 后端层级匹配（含 学业/高数 等子标签）
    queryFn: () => todoApi.list({ status: "all", tag: STUDY_TAG, limit: 200 }),
  });

  const { pending, unscheduled, done, archived } = useMemo(() => {
    const all = data?.items ?? [];
    const p: TodoItem[] = [];
    const u: TodoItem[] = [];
    const d: TodoItem[] = [];
    const a: TodoItem[] = [];
    // ★ 2026-10-02（主人）：已完成满 N 天的摘到「归档」，**不再出现在这里**。
    //   判据同后端（见 todo/archive.ts 的说明）—— 否则展开已完成还是老样子。
    for (const it of all) {
      if (!it.done) {
        if (it.due_at) p.push(it);
        else u.push(it);
      } else if (isArchived(it)) {
        a.push(it);
      } else {
        d.push(it);
      }
    }
    // ★ 最急在最上：due_at 升序
    p.sort((a, b) => new Date(a.due_at as string).getTime() - new Date(b.due_at as string).getTime());
    return { pending: p, unscheduled: u, done: d, archived: a };
  }, [data]);

  if (isLoading) {
    return (
      <div className="todo-list study-win">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} height={44} />
        ))}
      </div>
    );
  }
  if (error) return <ErrorState error={error} onRetry={() => refetch()} />;

  if (pending.length === 0 && unscheduled.length === 0 && done.length === 0) {
    return (
      <EmptyState
        text="还没有学业待办"
        hint={`建待办时打上「${STUDY_TAG}」标签即可（如 ${STUDY_TAG}/高数）—— 也可直接对我说：帮我记一个高数作业，下周三交`}
      />
    );
  }

  const renderRow = (it: TodoItem) => {
    const badge = dueBadge(it.due_at);
    const course = courseOf(it);
    return (
      <div key={it.id} className="study-row">
        <div className="study-row__meta">
          {course && <span className="study-chip">{course}</span>}
          {badge && (
            <span className={`study-badge study-badge--${badge.level}`}>{badge.text}</span>
          )}
        </div>
        <ItemRow item={it} />
      </div>
    );
  };

  return (
    <div className="todo-list study-win" data-testid="study-app">
      {pending.length > 0 && (
        <>
          <div className="study-section">⏰ 最急</div>
          {pending.map(renderRow)}
        </>
      )}
      {unscheduled.length > 0 && (
        <>
          <div className="study-section">📌 未排期</div>
          {unscheduled.map(renderRow)}
        </>
      )}
      {done.length > 0 && (
        <details className="study-done" data-testid="study-done">
          <summary>✅ 已完成（{done.length}）</summary>
          {done.map(renderRow)}
        </details>
      )}
      {/* ★ 2026-10-02（主人）：第三栏「归档」—— 打勾满 N 天的已完成项。
          与「已完成」严格互斥（归档的不在这里，这里的没归档），
          故两处的条数不会重复计算。 */}
      {archived.length > 0 && (
        <details className="study-done study-archived" data-testid="study-archived">
          <summary>
            🗄 归档（{archived.length}）· 已完成满 {ARCHIVE_AFTER_DAYS} 天自动收进来
          </summary>
          {archived.map(renderRow)}
        </details>
      )}
    </div>
  );
}
