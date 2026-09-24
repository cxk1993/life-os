import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { usePluginEvent } from "@/shared/api/events";
import { ApiError } from "@/shared/api/client";
import { habitsApi } from "./api";
import HabitRow from "./HabitRow";
import { loadPrefs, savePrefs, type HabitsPrefs } from "./prefs";
import "./habits.css";

function errText(e: unknown): string {
  if (e instanceof ApiError) return e.detail || e.title;
  return e instanceof Error ? e.message : "请求失败";
}

/** 习惯打卡主界面：快速添加 + 今日列表。 */
export default function HabitsApp() {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [prefs, setPrefs] = useState<HabitsPrefs>(() => loadPrefs());

  const invalidate = () => qc.invalidateQueries({ queryKey: ["habits"] });
  usePluginEvent("habits.habit.created", invalidate);
  usePluginEvent("habits.habit.updated", invalidate);
  usePluginEvent("habits.log.checked", invalidate);
  usePluginEvent("habits.log.unchecked", invalidate);

  const { data: habits, isLoading } = useQuery({
    queryKey: ["habits", "list", prefs.showArchived],
    queryFn: () => habitsApi.list(prefs.showArchived),
  });

  const patchPrefs = (p: Partial<HabitsPrefs>) => {
    const next = { ...prefs, ...p };
    setPrefs(next);
    savePrefs(next);
  };

  const createMut = useMutation({
    mutationFn: (n: string) => habitsApi.create({ name: n }),
    onSuccess: () => {
      setName("");
      setErr(null);
      invalidate();
    },
    onError: (e) => setErr(errText(e)),
  });

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const n = name.trim();
    if (!n || createMut.isPending) return;
    createMut.mutate(n);
  };

  const list = habits ?? [];
  const doneCount = list.filter((h) => h.today_status === "done").length;

  return (
    <div className="habits-root">
      <form className="habits-add" onSubmit={submit}>
        <input
          className="habits-add__input"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="添加习惯，如：早睡 / 晨跑 / 冥想"
          aria-label="添加习惯"
        />
        <button
          className="btn btn--primary"
          type="submit"
          disabled={createMut.isPending || !name.trim()}
        >
          添加
        </button>
      </form>

      <div className="habits-toolbar">
        <div className="tiny" style={{ color: "var(--txt-faint)" }}>
          {list.length > 0 ? `今日 ${doneCount}/${list.length}` : ""}
        </div>
        <label className="tiny" style={{ color: "var(--txt-faint)" }}>
          <input
            type="checkbox"
            checked={prefs.showArchived}
            onChange={(e) => patchPrefs({ showArchived: e.target.checked })}
            aria-label="显示已归档"
          />{" "}
          显示已归档
        </label>
      </div>
      {err ? (
        <div className="tiny habits-err" role="alert">
          {err}
        </div>
      ) : null}

      <div className="habits-list">
        {isLoading ? (
          <div className="empty">
            <div className="empty__text">加载中…</div>
          </div>
        ) : list.length === 0 ? (
          <div className="empty">
            <div className="empty__icon" aria-hidden>
              ○
            </div>
            <div className="empty__text">还没有习惯</div>
            <div className="empty__hint">在上方输入一个想坚持的小事，点圆钮打卡</div>
          </div>
        ) : (
          list.map((h) => <HabitRow key={h.id} habit={h} />)
        )}
      </div>
    </div>
  );
}
