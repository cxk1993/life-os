import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { todoApi, type TodoItem, type Priority } from "./api";

const PRIORITY_LABEL: Record<Priority, string> = {
  high: "高",
  medium: "中",
  low: "低",
};

function formatDue(dueAt: string | null): string | null {
  if (!dueAt) return null;
  const d = new Date(dueAt);
  if (Number.isNaN(d.getTime())) return null;
  const pad = (n: number) => String(n).padStart(2, "0");
  const date = `${d.getMonth() + 1}-${pad(d.getDate())}`;
  const hasTime = d.getHours() !== 0 || d.getMinutes() !== 0;
  return hasTime ? `${date} ${pad(d.getHours())}:${pad(d.getMinutes())}` : date;
}

interface Props {
  item: TodoItem;
}

/**
 * 一行待办：勾选框 + 文本（可内联编辑）+ 标签 + 优先级 + 截止 + 删除。
 * 乐观更新：toggle / 编辑 立刻反映到本地缓存，回滚在 onError 处理。
 * 逾期仅用温和的 🕘 标识，不做红字轰炸（主人明确偏好极简不制造焦虑）。
 */
export default function ItemRow({ item }: Props) {
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(item.text);

  const toggleMut = useMutation({
    mutationFn: () => todoApi.toggle(item.id),
    onMutate: async () => {
      await qc.cancelQueries({ queryKey: ["todo"] });
      const prev = qc.getQueriesData<{ items: TodoItem[] }>({ queryKey: ["todo"] });
      qc.setQueriesData<{ items: TodoItem[] }>({ queryKey: ["todo"] }, (old) =>
        old
          ? {
              ...old,
              items: old.items.map((i) =>
                i.id === item.id
                  ? {
                      ...i,
                      done: !i.done,
                      done_at: !i.done ? new Date().toISOString() : null,
                    }
                  : i,
              ),
            }
          : old,
      );
      return { prev };
    },
    onError: (_e, _v, ctx) => {
      ctx?.prev?.forEach(([key, data]) => qc.setQueryData(key, data));
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ["todo"] }),
  });

  const updateMut = useMutation({
    mutationFn: (body: Partial<TodoItem>) => todoApi.update(item.id, body),
    onMutate: async (body) => {
      await qc.cancelQueries({ queryKey: ["todo"] });
      const prev = qc.getQueriesData<{ items: TodoItem[] }>({ queryKey: ["todo"] });
      qc.setQueriesData<{ items: TodoItem[] }>({ queryKey: ["todo"] }, (old) =>
        old
          ? { ...old, items: old.items.map((i) => (i.id === item.id ? { ...i, ...body } : i)) }
          : old,
      );
      return { prev };
    },
    onError: (_e, _v, ctx) => {
      ctx?.prev?.forEach(([key, data]) => qc.setQueryData(key, data));
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ["todo"] }),
  });

  const deleteMut = useMutation({
    mutationFn: () => todoApi.remove(item.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["todo"] }),
  });

  const due = formatDue(item.due_at);
  const now = Date.now();
  const overdue = !item.done && item.due_at != null && new Date(item.due_at).getTime() < now;

  const saveEdit = () => {
    const t = draft.trim();
    if (t && t !== item.text) updateMut.mutate({ text: t });
    setEditing(false);
  };

  return (
    <div className={`todo-row${item.done ? " todo-row--done" : ""}`}>
      <button
        className="todo-row__check"
        aria-label={item.done ? "标记为未完成" : "标记为完成"}
        aria-pressed={item.done}
        onClick={() => toggleMut.mutate()}
      >
        {item.done ? "✓" : ""}
      </button>

      <div className="todo-row__main">
        {editing ? (
          <input
            className="todo-row__edit"
            value={draft}
            autoFocus
            onChange={(e) => setDraft(e.target.value)}
            onBlur={saveEdit}
            onKeyDown={(e) => {
              if (e.key === "Enter") saveEdit();
              if (e.key === "Escape") setEditing(false);
            }}
          />
        ) : (
          <span
            className="todo-row__text"
            onDoubleClick={() => {
              setDraft(item.text);
              setEditing(true);
            }}
            title="双击编辑"
          >
            {item.text}
          </span>
        )}

        <div className="todo-row__meta">
          {item.priority ? (
            <span className={`todo-pill todo-pill--${item.priority}`}>
              {PRIORITY_LABEL[item.priority]}
            </span>
          ) : null}
          {item.tags.map((t) => (
            <span key={t} className="todo-pill todo-pill--tag">
              #{t}
            </span>
          ))}
          {due ? (
            <span className={`todo-pill${overdue ? " todo-pill--overdue" : ""}`}>🕘 {due}</span>
          ) : null}
          {item.recur_rule ? <span className="todo-pill todo-pill--recur">🔁 周期</span> : null}
        </div>
      </div>

      <button
        className="btn btn--danger todo-row__del"
        aria-label="删除"
        onClick={() => deleteMut.mutate()}
      >
        删除
      </button>
    </div>
  );
}
