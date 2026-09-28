import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Tabs } from "@/shared/components/Tabs";
import { usePluginEvent } from "@/shared/api/events";
import { useTodoUI, type TodoView } from "./state";
import QuickAdd from "./QuickAdd";
import TodayView from "./views/TodayView";
import AllView from "./views/AllView";
import RecurringView from "./views/RecurringView";
import { todoApi } from "./api";

const STUDY_TAG = "学业";

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
 * - ★ 2026-09-26：右上角「只看学业」快捷筛选（层级标签：学业 / 学业/高数 …）。
 */
export default function TodoApp() {
  const qc = useQueryClient();
  const view = useTodoUI((s) => s.view);
  const setView = useTodoUI((s) => s.setView);
  // ★ 2026-09-26（astrbot · 主人令「学业页」）：**快捷筛选器**（轻入口）——
  //   与 schedule 容器的「学业」专页（重入口）形成一轻一重双入口，不重复。
  const filterTag = useTodoUI((s) => s.filterTag);
  const setFilterTag = useTodoUI((s) => s.setFilterTag);
  const studyOnly = filterTag === STUDY_TAG;

  // ★ 2026-09-28（主人令「通过 tag 的筛选，动态的一键查看与分类」）：
  //   标签条由**硬编码**改为**数据驱动** —— 数据源 = GET /api/v1/todo/tags
  //   （同一端点也是 AI 的 MCP 工具 todo_tag_read：**一份数据喂两边**）
  const { data: tagCounts } = useQuery({
    queryKey: ["todo", "tags"],
    queryFn: () => todoApi.tags(),
  });
  // 学业已由左侧固定按钮承担，这里不重复列，免得同一个筛选出现两个入口
  const tagChips = (tagCounts ?? []).filter((c) => c.tag !== STUDY_TAG);

  // 后端写入会推 todo.item.* 事件，收到即失效本地缓存（SSE 自动重连）。
  usePluginEvent("todo.item.created", () => qc.invalidateQueries({ queryKey: ["todo"] }));
  usePluginEvent("todo.item.updated", () => qc.invalidateQueries({ queryKey: ["todo"] }));
  usePluginEvent("todo.item.completed", () => qc.invalidateQueries({ queryKey: ["todo"] }));

  return (
    <div className="todo-root">
      <QuickAdd />
      <div className="todo-toolbar">
        <Tabs tabs={TABS} active={view} onChange={(id) => setView(id as TodoView)} />
        <button
          type="button"
          className={studyOnly ? "todo-study-filter todo-study-filter--on" : "todo-study-filter"}
          aria-pressed={studyOnly}
          data-testid="todo-study-filter"
          onClick={() => setFilterTag(studyOnly ? null : STUDY_TAG)}
        >
          只看学业
        </button>
      </div>
      {tagChips.length > 0 && (
        <div className="todo-tagbar" data-testid="todo-tagbar">
          {tagChips.map((c) => {
            const on = filterTag === c.tag;
            return (
              <button
                key={c.tag}
                type="button"
                className={on ? "todo-tagchip todo-tagchip--on" : "todo-tagchip"}
                aria-pressed={on}
                data-testid={`todo-tagchip-${c.tag}`}
                title={`#${c.tag} 未完成 ${c.todo} · 已完成 ${c.done}`}
                onClick={() => {
                  setFilterTag(on ? null : c.tag);
                  // 一键查看：点标签就直接切到「全部」并把筛子筛上
                  if (!on) setView("all");
                }}
              >
                #{c.tag}
                {c.todo > 0 ? <span className="todo-tagchip__n">{c.todo}</span> : null}
              </button>
            );
          })}
        </div>
      )}
      {view === "today" && <TodayView />}
      {view === "all" && <AllView />}
      {view === "recurring" && <RecurringView />}
    </div>
  );
}
