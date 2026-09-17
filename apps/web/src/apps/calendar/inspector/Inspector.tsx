/**
 * 右侧属性面板：编辑选中事项（标题 / 颜色 / 起止 / 全天 / 地点 / 备注），
 * 并列出子块，支持子块的改名 / 删除，以及给父块追加子块。
 * 选中项若是子块，则通过 onPatchChild 走独立的子块接口。
 */

import { useEffect, useState } from "react";
import type { CalendarEvent, EventPatch } from "../api";
import { EVENT_COLORS } from "./QuickCard";

interface Props {
  selected: CalendarEvent | null;
  parentOfSelected: CalendarEvent | null;
  onPatch: (id: string, patch: EventPatch) => void;
  onPatchChild: (parentId: string, childId: string, patch: EventPatch) => void;
  onAddChild: (
    parentId: string,
    input: { title: string; start_at: string; end_at: string },
  ) => void;
  onDelete: (id: string) => void;
  onDeleteChild: (parentId: string, childId: string) => void;
  onSelect: (id: string | null) => void;
}

function toLocalInput(iso: string): string {
  const d = new Date(iso);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(
    d.getMinutes(),
  )}`;
}

export function Inspector({
  selected,
  parentOfSelected,
  onPatch,
  onPatchChild,
  onAddChild,
  onDelete,
  onDeleteChild,
  onSelect,
}: Props) {
  const [title, setTitle] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [allDay, setAllDay] = useState(false);
  const [location, setLocation] = useState("");
  const [note, setNote] = useState("");

  useEffect(() => {
    if (!selected) return;
    setTitle(selected.title);
    setStart(toLocalInput(selected.start_at));
    setEnd(toLocalInput(selected.end_at));
    setAllDay(selected.all_day);
    setLocation(selected.location ?? "");
    setNote(selected.note ?? "");
  }, [selected?.id, selected?.title, selected?.start_at, selected?.end_at, selected?.all_day]);

  if (!selected) {
    return (
      <aside className="cal-inspector empty">
        <div className="cal-inspector-empty">选中一个事项以查看 / 编辑详情</div>
      </aside>
    );
  }

  const isChild = !!parentOfSelected;
  const patch = (p: EventPatch) => {
    if (isChild && parentOfSelected) onPatchChild(parentOfSelected.id, selected.id, p);
    else onPatch(selected.id, p);
  };

  return (
    <aside className="cal-inspector">
      <header className="cal-inspector-head">
        <span className="cal-inspector-kind">{isChild ? "子块" : "事项"}</span>
        {isChild ? (
          <button className="cal-link" onClick={() => onSelect(parentOfSelected!.id)}>
            ↑ 回到父块
          </button>
        ) : null}
        <button className="cal-inspector-del" onClick={() => onDelete(selected.id)}>
          删除
        </button>
      </header>

      <label className="cal-field">
        <span>标题</span>
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onBlur={() => title !== selected.title && patch({ title })}
          onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
        />
      </label>

      <div className="cal-field">
        <span>颜色</span>
        <div className="cal-swatches-row">
          {EVENT_COLORS.map((c) => (
            <button
              key={c}
              className={"cal-swatch" + (selected.color === c ? " active" : "")}
              style={{ background: c }}
              onClick={() => patch({ color: c })}
            />
          ))}
        </div>
      </div>

      <label className="cal-field">
        <span>开始</span>
        <input
          type="datetime-local"
          value={start}
          onChange={(e) => setStart(e.target.value)}
          onBlur={() => {
            if (start && start !== toLocalInput(selected.start_at))
              patch({ start_at: new Date(start).toISOString() });
          }}
        />
      </label>
      <label className="cal-field">
        <span>结束</span>
        <input
          type="datetime-local"
          value={end}
          onChange={(e) => setEnd(e.target.value)}
          onBlur={() => {
            if (end && end !== toLocalInput(selected.end_at))
              patch({ end_at: new Date(end).toISOString() });
          }}
        />
      </label>

      <label className="cal-field-inline">
        <input
          type="checkbox"
          checked={allDay}
          onChange={(e) => {
            setAllDay(e.target.checked);
            patch({ all_day: e.target.checked });
          }}
        />
        <span>全天</span>
      </label>

      <label className="cal-field">
        <span>地点</span>
        <input
          value={location}
          placeholder="可选"
          onChange={(e) => setLocation(e.target.value)}
          onBlur={() => patch({ location: location || null })}
        />
      </label>
      <label className="cal-field">
        <span>备注</span>
        <textarea
          value={note}
          placeholder="可选"
          onChange={(e) => setNote(e.target.value)}
          onBlur={() => patch({ note: note || null })}
        />
      </label>

      {/* 子块管理（仅父块显示） */}
      {!isChild ? (
        <div className="cal-children">
          <div className="cal-children-head">
            <span>子块（{selected.children?.length ?? 0}）</span>
            <button
              className="cal-link"
              onClick={() =>
                onAddChild(selected.id, {
                  title: "新子块",
                  start_at: selected.start_at,
                  end_at: selected.end_at,
                })
              }
            >
              + 加子块
            </button>
          </div>
          <ul className="cal-children-list">
            {(selected.children ?? []).map((ch) => (
              <li key={ch.id} className="cal-child-row">
                <span
                  className="cal-child-dot"
                  style={{ background: ch.color || "var(--accent)" }}
                />
                <button className="cal-child-name" onClick={() => onSelect(ch.id)}>
                  {ch.title}
                </button>
                <button className="cal-child-del" onClick={() => onDeleteChild(selected.id, ch.id)}>
                  删
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </aside>
  );
}
