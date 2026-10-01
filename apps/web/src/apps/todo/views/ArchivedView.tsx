/**
 * 归档视图（★ 2026-10-02 · 主人令）—— 待办页的「第三栏」。
 *
 * 主人原话：「已经做完的待办，最好能够有一个归档的二级分类 … 打钩完成的日期
 * 过了 7 天，就可以自动归档、自动隐藏；展开已完成的那小列表就不会显示了，
 * 而是自动有一个第三栏『归档』」。
 *
 * ── 这个视图为什么这么薄 ──────────────────────────────────────────
 * **归档不是一种状态，是时间的函数。** 后端按 `done_at` 老化算
 * （`status=archived`，阈值见 services/api/modules/todo/service.py 的
 * `ARCHIVE_AFTER_DAYS`），**没有归档动作、也没有 archived 字段要维护** ——
 * 所以这里只负责取数、按完成时间倒序展示，一行写入逻辑都不该有。
 * 若哪天有人往这里加「归档按钮」，那说明归档被改成了手动状态，与本设计相悖。
 *
 * ⚠️ 别把这里做成「删除」。归档是**换栏位**，数据仍在库里、随时可查；
 * 删掉才是真没了。主人要的是「眼不见但不丢」。
 */
import { useQuery } from "@tanstack/react-query";
import { todoApi } from "../api";
import ItemRow from "../ItemRow";
import ErrorState from "../ErrorState";
import { EmptyState } from "@/shared/components/EmptyState";
import { Skeleton } from "@/shared/components/Skeleton";
import { TODO_KEY_ROOT } from "../keys";
import { ARCHIVE_AFTER_DAYS } from "../constants";

/** 本地化的完成日期（归档项最有用的那一条信息就是「什么时候打完的」）。 */
function doneLabel(doneAt: string | null): string | null {
  if (!doneAt) return null;
  const d = new Date(doneAt);
  if (Number.isNaN(d.getTime())) return null;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} 完成`;
}

export default function ArchivedView() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: [TODO_KEY_ROOT, "archived"],
    queryFn: () => todoApi.list({ status: "archived", limit: 200 }),
  });

  if (isLoading) {
    return (
      <div className="todo-list">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} height={40} />
        ))}
      </div>
    );
  }
  if (error) return <ErrorState error={error} onRetry={() => refetch()} />;

  const items = data?.items ?? [];

  if (items.length === 0) {
    return (
      <EmptyState
        text="归档还是空的"
        hint={`已完成的待办在打勾满 ${ARCHIVE_AFTER_DAYS} 天后会自动移到这里 —— 不用手动整理`}
      />
    );
  }

  // 最近归档的在最上（完成时间倒序）
  const sorted = [...items].sort(
    (a, b) => new Date(b.done_at ?? 0).getTime() - new Date(a.done_at ?? 0).getTime(),
  );

  return (
    <div className="todo-list" data-testid="todo-archived">
      <div className="todo-archived__hint">
        ✅ 已完成满 {ARCHIVE_AFTER_DAYS} 天的待办会自动归档到这里（数据没删，随时可查）
      </div>
      {sorted.map((it) => (
        <div key={it.id} className="todo-archived__row">
          {doneLabel(it.done_at) && (
            <span className="todo-archived__when">{doneLabel(it.done_at)}</span>
          )}
          <ItemRow item={it} />
        </div>
      ))}
    </div>
  );
}
