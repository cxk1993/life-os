import { useQueryClient } from "@tanstack/react-query";
import { Tabs } from "@/shared/components/Tabs";
import { usePluginEvent } from "@/shared/api/events";
import { useTodoUI, type TodoView } from "./state";
import QuickAdd from "./QuickAdd";
import TodayView from "./views/TodayView";
import AllView from "./views/AllView";
import RecurringView from "./views/RecurringView";

const TABS: { id: TodoView; label: string }[] = [
  { id: "today", label: "今日" },
  { id: "all", label: "全部" },
  { id: "recurring", label: "周期" },
];

/**
 * 待办窗口主界面。
 * - 顶部快速添加（语法糖在服务端解析）。
 * - 三个视图用 Tabs 切换（纯 UI 状态在 state.ts 的 useTodoUI）。
 * - 订阅内核 SSE 事件做增量刷新（created/updated/completed）。
 */
export default function TodoApp() {
  const qc = useQueryClient();
  const view = useTodoUI((s) => s.view);
  const setView = useTodoUI((s) => s.setView);

  // 后端写入会推 todo.item.* 事件，收到即失效本地缓存（SSE 自动重连）。
  usePluginEvent("todo.item.created", () =>
    qc.invalidateQueries({ queryKey: ["todo"] }),
  );
  usePluginEvent("todo.item.updated", () =>
    qc.invalidateQueries({ queryKey: ["todo"] }),
  );
  usePluginEvent("todo.item.completed", () =>
    qc.invalidateQueries({ queryKey: ["todo"] }),
  );

  return (
    <div className="todo-root">
      <QuickAdd />
      <Tabs
        tabs={TABS}
        active={view}
        onChange={(id) => setView(id as TodoView)}
      />
      {view === "today" && <TodayView />}
      {view === "all" && <AllView />}
      {view === "recurring" && <RecurringView />}
    </div>
  );
}
