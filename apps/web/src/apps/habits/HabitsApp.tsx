import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { usePluginEvent } from "@/shared/api/events";
import { habitsApi } from "./api";
import HabitRow from "./HabitRow";
import "./habits.css";

/** 习惯打卡主界面：快速添加 + 今日列表。 */
export default function HabitsApp() {
  const qc = useQueryClient();
  const [name, setName] = useState("");

  const invalidate = () => qc.invalidateQueries({ queryKey: ["habits"] });
  usePluginEvent("habits.habit.created", invalidate);
  usePluginEvent("habits.habit.updated", invalidate);
  usePluginEvent("habits.log.checked", invalidate);
  usePluginEvent("habits.log.unchecked", invalidate);

  const { data: habits, isLoading } = useQuery({
    queryKey: ["habits", "list"],
    queryFn: () => habitsApi.list(),
  });

  const createMut = useMutation({
    mutationFn: (n: string) => habitsApi.create({ name: n }),
    onSuccess: () => {
      setName("");
      invalidate();
    },
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

      <div className="tiny" style={{ color: "var(--txt-faint)" }}>
        {list.length > 0 ? `今日 ${doneCount}/${list.length}` : ""}
      </div>

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
