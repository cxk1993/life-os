import { useQuery } from "@tanstack/react-query";
import { todoApi } from "../api";
import ItemRow from "../ItemRow";
import ErrorState from "../ErrorState";
import { EmptyState } from "@/shared/components/EmptyState";
import { Skeleton } from "@/shared/components/Skeleton";
import { useTodoUI } from "../state";
import { TODO_KEY_ROOT } from "../keys";

/**
 * 全部视图：有价值的待办（**不含已归档的**），可按标签过滤。
 * 服务端不做标签过滤时，这里在前端按 filterTag 过滤（filterTag 来自顶部标签条）。
 *
 * ★ 2026-10-02（主人「已完成满 7 天自动隐藏」）：取 `status=active` 而**不是** `all`
 *   —— `all` 是含归档的「一切」（供归档视图与学业页分组用），主列表用它会
 *   把几十天前打完的旧账又摆出来，正是主人要消除的观感。要看归档请切「归档」栏。
 */
export default function AllView() {
  const filterTag = useTodoUI((s) => s.filterTag);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: [TODO_KEY_ROOT, "all", filterTag],
    queryFn: () => todoApi.list({ status: "active", limit: 200 }),
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

  // ★ 2026-09-26（astrbot · 主人「学业页」）：标签过滤支持**层级** ——
  //   filterTag="学业" 命中 `学业` 与 `学业/高数`、`学业/大物`（与后端 tag_hit 同语义）。
  const tagHit = (tags: string[], q: string) =>
    tags.some((t) => t === q || t.startsWith(q + "/"));
  const items = data?.items.filter((it) => !filterTag || tagHit(it.tags ?? [], filterTag)) ?? [];

  if (items.length === 0) {
    return (
      <EmptyState
        text={filterTag ? `没有 #${filterTag} 的待办` : "还没有任何待办"}
        hint="在上方快速添加一句，支持 @日期 #标签 !优先级 语法糖"
      />
    );
  }

  return (
    <div className="todo-list">
      {items.map((it) => (
        <ItemRow key={it.id} item={it} />
      ))}
    </div>
  );
}
