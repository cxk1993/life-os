import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ApiError } from "@/shared/api/client";
import { habitsApi, type Habit, type HabitUpdateBody } from "./api";

function errText(e: unknown): string {
  if (e instanceof ApiError) return e.detail || e.title;
  return e instanceof Error ? e.message : "操作失败";
}

const WEEKDAY_LBL = ["一", "二", "三", "四", "五", "六", "日"];

/** 设计令牌色板（自定义颜色只认令牌名，不收 #hex——铁律）。 */
const COLOR_TOKENS = [
  { id: "var(--accent)", label: "强调" },
  { id: "var(--ok)", label: "达成" },
  { id: "var(--info)", label: "信息" },
  { id: "var(--warn)", label: "提醒" },
  { id: "var(--danger)", label: "重要" },
  { id: "var(--txt-faint)", label: "淡雅" },
];

interface Props {
  habit: Habit;
  onDone: () => void;
}

/** 习惯自定义面板：目标文案 / 色令牌 / 休息日 / 提醒时刻（高度自定义入口）。 */
export default function HabitEdit({ habit, onDone }: Props) {
  const qc = useQueryClient();
  const [name, setName] = useState(habit.name);
  const [target, setTarget] = useState(habit.target);
  const [color, setColor] = useState(habit.color);
  const [reminder, setReminder] = useState(habit.reminder_time);
  const [rest, setRest] = useState<number[]>(habit.rest_weekdays);
  const [err, setErr] = useState<string | null>(null);

  const saveMut = useMutation({
    mutationFn: (body: HabitUpdateBody) => habitsApi.update(habit.id, body),
    onSuccess: () => {
      setErr(null);
      qc.invalidateQueries({ queryKey: ["habits"] });
      onDone();
    },
    onError: (e) => setErr(errText(e)),
  });

  const toggleRest = (d: number) =>
    setRest((r) => (r.includes(d) ? r.filter((x) => x !== d) : [...r, d].sort()));

  return (
    <div className="habit-edit" role="group" aria-label={`自定义 ${habit.name}`}>
      <label className="habit-edit__row">
        <span>名称</span>
        <input value={name} onChange={(e) => setName(e.target.value)} aria-label="习惯名称" />
      </label>
      <label className="habit-edit__row">
        <span>目标</span>
        <input
          value={target}
          placeholder="如：23:30 前 / 每天 8 杯水"
          onChange={(e) => setTarget(e.target.value)}
          aria-label="习惯目标"
        />
      </label>
      <div className="habit-edit__row">
        <span>颜色</span>
        <div className="habit-edit__colors">
          {COLOR_TOKENS.map((c) => (
            <button
              key={c.id}
              type="button"
              className={"habit-swatch" + (color === c.id ? " habit-swatch--on" : "")}
              style={{ background: c.id }}
              aria-label={c.label}
              aria-pressed={color === c.id}
              onClick={() => setColor(c.id)}
            />
          ))}
        </div>
      </div>
      <div className="habit-edit__row">
        <span>休息</span>
        <div className="habit-edit__days">
          {WEEKDAY_LBL.map((lb, d) => (
            <button
              key={d}
              type="button"
              className={"habit-day" + (rest.includes(d) ? " habit-day--on" : "")}
              aria-pressed={rest.includes(d)}
              aria-label={`休息 ${lb}`}
              onClick={() => toggleRest(d)}
            >
              {lb}
            </button>
          ))}
        </div>
      </div>
      <label className="habit-edit__row">
        <span>提醒</span>
        <input
          type="time"
          value={reminder}
          aria-label="提醒时刻"
          onChange={(e) => setReminder(e.target.value)}
        />
      </label>
      <div className="habit-edit__actions">
        <button
          type="button"
          className="btn btn--primary"
          disabled={saveMut.isPending || !name.trim()}
          onClick={() =>
            saveMut.mutate({
              name: name.trim(),
              target,
              color,
              reminder_time: reminder,
              rest_weekdays: rest,
            })
          }
        >
          保存
        </button>
        <button type="button" className="btn" onClick={onDone}>
          取消
        </button>
      </div>
      {err ? (
        <div className="tiny habits-err" role="alert">
          {err}
        </div>
      ) : null}
    </div>
  );
}
