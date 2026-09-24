import { useQuery } from "@tanstack/react-query";
import { todoApi } from "../api";
import ItemRow from "../ItemRow";
import ErrorState from "../ErrorState";
import { EmptyState } from "@/shared/components/EmptyState";
import { Skeleton } from "@/shared/components/Skeleton";

/**
 * 周期视图：所有带 recur_rule 的待办（周期任务）。
 * 后端没有专门的 recur 过滤，这里取全部后前端筛 recur_rule 非空。
 */
export default function RecurringView() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["todo", "recurring"],
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

  const items = data?.items.filter((it) => it.recur_rule) ?? [];

  if (items.length === 0) {
    return (
      <EmptyState
        text="还没有周期任务"
        hint="添加时带 🔁 语法，例如：每周备份 🔁 every week on Sunday"
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
