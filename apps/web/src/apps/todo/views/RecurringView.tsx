import { useQuery } from "@tanstack/react-query";
import { todoApi } from "../api";
import ItemRow from "../ItemRow";
import ErrorState from "../ErrorState";
import { EmptyState } from "@/shared/components/EmptyState";
import { Skeleton } from "@/shared/components/Skeleton";
import { TODO_KEY_ROOT } from "../keys";

/**
 * 周期视图：所有带 recur_rule 的待办（周期任务）。
 * 后端没有专门的 recur 过滤，这里取回来后前端筛 recur_rule 非空。
 *
 * ★ 2026-10-02（主人令「已完成满 7 天自动隐藏」）：取 `status=active` ——
 *   周期任务每完成一次会生成下一实例，旧的已完成实例过 7 天即归档；
 *   用 `all` 会让历史实例无限堆在这个页面里。
 */
export default function RecurringView() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: [TODO_KEY_ROOT, "recurring"],
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
