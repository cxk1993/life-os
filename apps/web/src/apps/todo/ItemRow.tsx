import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { todoApi, type TodoItem, type Priority } from "./api";
import { TODO_KEY_ROOT } from "./keys";

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
  // ★ 2026-09-28（主人令「最好能给每个事项加标签 tag」）：
  //   此前 `#标签` 语法糖只在**新建**时生效 —— 已存在的事项改不了标签。
  //   这里补一个行内标签编辑（点「＋标签」），空格/逗号分隔，可删可加。
  const [tagEditing, setTagEditing] = useState(false);
  const [tagDraft, setTagDraft] = useState(item.tags.join(" "));

  const toggleMut = useMutation({
    mutationFn: () => todoApi.toggle(item.id),
    onMutate: async () => {
      await qc.cancelQueries({ queryKey: [TODO_KEY_ROOT] });
      const prev = qc.getQueriesData<{ items: TodoItem[] }>({ queryKey: [TODO_KEY_ROOT] });
      qc.setQueriesData<{ items: TodoItem[] }>({ queryKey: [TODO_KEY_ROOT] }, (old) =>
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
    onSettled: () => qc.invalidateQueries({ queryKey: [TODO_KEY_ROOT] }),
  });

  const updateMut = useMutation({
    mutationFn: (body: Partial<TodoItem>) => todoApi.update(item.id, body),
    onMutate: async (body) => {
      await qc.cancelQueries({ queryKey: [TODO_KEY_ROOT] });
      const prev = qc.getQueriesData<{ items: TodoItem[] }>({ queryKey: [TODO_KEY_ROOT] });
      qc.setQueriesData<{ items: TodoItem[] }>({ queryKey: [TODO_KEY_ROOT] }, (old) =>
        old
          ? { ...old, items: old.items.map((i) => (i.id === item.id ? { ...i, ...body } : i)) }
          : old,
      );
      return { prev };
    },
    onError: (_e, _v, ctx) => {
      ctx?.prev?.forEach(([key, data]) => qc.setQueryData(key, data));
    },
    onSettled: () => qc.invalidateQueries({ queryKey: [TODO_KEY_ROOT] }),
  });

  const deleteMut = useMutation({
    mutationFn: () => todoApi.remove(item.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: [TODO_KEY_ROOT] }),
  });

  const due = formatDue(item.due_at);
  const now = Date.now();
  const overdue = !item.done && item.due_at != null && new Date(item.due_at).getTime() < now;

  const saveEdit = () => {
    const t = draft.trim();
    if (t && t !== item.text) updateMut.mutate({ text: t });
    setEditing(false);
  };

  const saveTags = () => {
    const next = tagDraft
      .split(/[\s,，]+/)
      .map((s) => s.replace(/^#/, "").trim())
      .filter(Boolean);
    // 去重保序（与后端 tags_to_json 口径一致）
    const uniq = Array.from(new Set(next));
    const same =
      uniq.length === item.tags.length && uniq.every((t, i) => t === item.tags[i]);
    if (!same) updateMut.mutate({ tags: uniq });
    setTagEditing(false);
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
          {tagEditing ? (
            <input
              className="todo-tag-edit"
              autoFocus
              value={tagDraft}
              data-testid="todo-tag-edit"
              placeholder="标签，空格分隔（如 学业/高数 副业）"
              onChange={(e) => setTagDraft(e.target.value)}
              onBlur={saveTags}
              onKeyDown={(e) => {
                if (e.key === "Enter") saveTags();
                if (e.key === "Escape") {
                  setTagDraft(item.tags.join(" "));
                  setTagEditing(false);
                }
              }}
            />
          ) : (
            <>
              {item.tags.map((t) => (
                <span key={t} className="todo-pill todo-pill--tag">
                  #{t}
                </span>
              ))}
              <button
                type="button"
                className="todo-tag-add"
                data-testid="todo-tag-add"
                title="编辑标签"
                onClick={() => {
                  setTagDraft(item.tags.join(" "));
                  setTagEditing(true);
                }}
              >
                ＋标签
              </button>
            </>
          )}
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
