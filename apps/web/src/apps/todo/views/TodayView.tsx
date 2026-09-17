import { useQuery } from "@tanstack/react-query";
import { todoApi } from "../api";
import ItemRow from "../ItemRow";
import ErrorState from "../ErrorState";
import { EmptyState } from "@/shared/components/EmptyState";
import { Skeleton } from "@/shared/components/Skeleton";

/** 本地今日 23:59:59 的 UTC ISO，作为 due_before 边界（含逾期项）。 */
function endOfTodayISO(): string {
  const d = new Date();
  d.setHours(23, 59, 59, 999);
  return d.toISOString();
}

/**
 * 今日视图：未完成且截止 <= 今日 23:59 的待办（自然包含逾期项）。
 * 处理三态：加载中 / 出错 / 空数据。
 */
export default function TodayView() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["todo", "today"],
    queryFn: () =>
      todoApi.list({ status: "todo", due_before: endOfTodayISO(), limit: 200 }),
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
  if (!data || data.items.length === 0) {
    return (
      <EmptyState
        text="今天没有待办"
        hint="在上方快速添加一句，支持 @日期 #标签 !优先级 语法糖"
      />
    );
  }

  return (
    <div className="todo-list">
      {data.items.map((it) => (
        <ItemRow key={it.id} item={it} />
      ))}
    </div>
  );
}
