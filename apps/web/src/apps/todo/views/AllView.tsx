import { useQuery } from "@tanstack/react-query";
import { todoApi } from "../api";
import ItemRow from "../ItemRow";
import ErrorState from "../ErrorState";
import { EmptyState } from "@/shared/components/EmptyState";
import { Skeleton } from "@/shared/components/Skeleton";
import { useTodoUI } from "../state";

/**
 * 全部视图：所有待办（含已完成），可按标签过滤。
 * 服务端不做标签过滤时，这里在前端按 filterTag 过滤（filterTag 来自顶部标签条）。
 */
export default function AllView() {
  const filterTag = useTodoUI((s) => s.filterTag);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["todo", "all", filterTag],
    queryFn: () => todoApi.list({ status: "all", limit: 200 }),
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

  // ★ 2026-09-26（astrbot · 主人令「学业页」）：标签过滤支持**层级** ——
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
