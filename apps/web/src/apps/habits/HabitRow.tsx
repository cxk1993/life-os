import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { habitsApi, type Habit } from "./api";

const WEEKDAY_LBL = ["一", "二", "三", "四", "五", "六", "日"];

/** 本地日历日 YYYY-MM-DD（打卡/取消打卡用，避免 UTC 跨日偏差）。 */
function localDay(d: Date = new Date()): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

interface Props {
  habit: Habit;
}

/** 一行习惯：打卡圆钮 + 名称/目标 + 连击 + 归档/删除。 */
export default function HabitRow({ habit }: Props) {
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);

  const invalidate = () => qc.invalidateQueries({ queryKey: ["habits"] });

  const checkMut = useMutation({
    mutationFn: () =>
      habit.today_status === "done"
        ? habitsApi.uncheck(habit.id, localDay())
        : habitsApi.checkin(habit.id),
    onMutate: () => setBusy(true),
    onSettled: () => {
      setBusy(false);
      invalidate();
    },
  });

  const archMut = useMutation({
    mutationFn: () => habitsApi.update(habit.id, { archived: true }),
    onSuccess: invalidate,
  });

  const delMut = useMutation({
    mutationFn: () => habitsApi.remove(habit.id),
    onSuccess: invalidate,
  });

  const done = habit.today_status === "done";
  const rest = habit.today_status === "rest";
  const restLbl =
    habit.rest_weekdays.length > 0
      ? `休 ${habit.rest_weekdays.map((d) => WEEKDAY_LBL[d]).join("")}`
      : null;

  return (
    <div
      className={"habit-row" + (done ? " habit-row--done" : "") + (rest ? " habit-row--rest" : "")}
    >
      <button
        type="button"
        className={"habit-row__check" + (done ? " habit-row__check--done" : "")}
        aria-label={done ? `取消打卡 ${habit.name}` : `打卡 ${habit.name}`}
        aria-pressed={done}
        disabled={busy}
        onClick={() => checkMut.mutate()}
      >
        {done ? "✓" : rest ? "休" : ""}
      </button>
      <div className="habit-row__main">
        <div className="habit-row__name" title={habit.name}>
          {habit.name}
        </div>
        <div className="habit-row__meta">
          {habit.target ? <span>{habit.target}</span> : null}
          {habit.streak > 0 ? (
            <span className="habit-row__streak">连续 {habit.streak} 天</span>
          ) : null}
          {restLbl ? <span>{restLbl}</span> : null}
        </div>
      </div>
      <button
        type="button"
        className="btn habit-row__del"
        aria-label={`归档 ${habit.name}`}
        disabled={archMut.isPending}
        onClick={() => archMut.mutate()}
      >
        归档
      </button>
      <button
        type="button"
        className="btn btn--danger habit-row__del"
        aria-label={`删除 ${habit.name}`}
        onClick={() => {
          if (window.confirm(`删除习惯「${habit.name}」？历史打卡也会一并删除。`)) {
            delMut.mutate();
          }
        }}
      >
        删除
      </button>
    </div>
  );
}
