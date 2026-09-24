import { useQuery } from "@tanstack/react-query";

import { ApiError } from "@/shared/api/client";
import { useDesktopStore } from "../../../kernel/store";
import { todoApi } from "../api";
import type { TodaySummary } from "../api";

/**
 * U3 · 桌面右栏 dock 卡（`desktop.dock-right` 扩展点，dock 数据规范 v1 首例）。
 *
 * 数据：`/api/v1/todo/today-summary`（规范 v1：{title, items≤5:[{text,state,count}], link} + done）。
 * 三态语义（★ 副总监铁律：「没装」≠「没数据」必须可区分）：
 *   404 → 「未安装 · 去安装」占位（不消失）
 *   200 空 → 「今日暂无待办」
 *   200 有 → 列表（逾期 alert 红色点 / 今日到期 due 蓝点）
 *   5xx  → 「暂时不可用」（≠ 没数据）
 */
export default function DockCard() {
  const openWindow = useDesktopStore((s) => s.openWindow);
  const { data, isError, isLoading } = useQuery({
    queryKey: ["todo", "today-summary"],
    queryFn: async (): Promise<TodaySummary | null> => {
      try {
        return await todoApi.todaySummary();
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) return null;
        throw e;
      }
    },
    retry: 1,
    refetchOnWindowFocus: false,
  });

  const items = data?.items ?? [];

  return (
    <div className="dock-card" data-testid="todo-dock-card">
      <button type="button" className="dock-card__head" onClick={() => openWindow("todo")}>
        <span>待办</span>
        {data?.title ? <span className="dock-card__sub">{data.title}</span> : null}
        {items.length > 0 ? <span className="dock-card__count">{items.length}</span> : null}
      </button>
      {isLoading ? (
        <div className="dock-card__empty">…</div>
      ) : isError ? (
        <div className="dock-card__empty" data-testid="todo-dock-err">
          暂时不可用
        </div>
      ) : data === null ? (
        <div className="dock-card__empty" data-testid="todo-dock-na">
          未安装 · 去安装
        </div>
      ) : items.length === 0 ? (
        <div className="dock-card__empty">今日暂无待办</div>
      ) : (
        <ul className="dock-card__list">
          {items.map((it, i) => (
            <li
              key={i}
              className={`dock-card__item${it.state === "alert" ? " is-alert" : ""}${
                it.state === "due" ? " is-due" : ""
              }`}
            >
              <span className="dock-card__dot" aria-hidden="true" />
              <span className="dock-card__txt">{it.text}</span>
              {typeof it.count === "number" ? (
                <span className="dock-card__cnt">{it.count}</span>
              ) : null}
            </li>
          ))}
          {typeof data?.done === "number" && data.done > 0 ? (
            <li className="dock-card__item is-done">
              <span className="dock-card__dot" aria-hidden="true" />
              <span className="dock-card__txt">已完成 {data.done} 项</span>
            </li>
          ) : null}
        </ul>
      )}
    </div>
  );
}
