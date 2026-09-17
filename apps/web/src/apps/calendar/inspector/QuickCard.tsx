/**
 * 悬浮交互卡片（主人明确要求「每个事项有自己的交互卡片」）。
 * 点击色块时从色块内弹出，提供改名 / 换色 / 定位 / 加子块 / 删除等快捷操作。
 * 纯展示 + 回调，不持有任何服务端状态。
 */

import { useEffect, useRef } from "react";
import type { CalendarEvent } from "../api";

/** 8 色设计令牌（与 tokens.css 的 --accent 体系对齐，仅用 token 名，不写死 #）。 */
export const EVENT_COLORS = [
  "var(--accent)",
  "var(--accent-2)",
  "var(--accent-3)",
  "var(--good)",
  "var(--warn)",
  "var(--danger)",
  "var(--info)",
  "var(--muted-fg)",
];

interface Props {
  event: CalendarEvent;
  onClose: () => void;
  onRename: (title: string) => void;
  onColor: (color: string) => void;
  onFocus: () => void;
  onAddChild: () => void;
  onDelete: () => void;
}

export function QuickCard({
  event,
  onClose,
  onRename,
  onColor,
  onFocus,
  onAddChild,
  onDelete,
}: Props) {
  const ref = useRef<HTMLDivElement>(null);

  // 点击卡片外部关闭
  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    const t = setTimeout(() => document.addEventListener("mousedown", onDown), 0);
    return () => {
      clearTimeout(t);
      document.removeEventListener("mousedown", onDown);
    };
  }, [onClose]);

  return (
    <div className="cal-quickcard" ref={ref} role="dialog" aria-label={`${event.title} 操作`}>
      <div className="cal-quickcard-head">
        <span
          className="cal-quickcard-dot"
          style={{ background: event.color || "var(--accent)" }}
        />
        <strong className="cal-quickcard-title" title={event.title}>
          {event.title}
        </strong>
        <button className="cal-quickcard-close" onClick={onClose} aria-label="关闭">
          ×
        </button>
      </div>

      <div className="cal-quickcard-row">
        <span className="cal-quickcard-k">时间</span>
        <span className="cal-quickcard-v">
          {event.start_at.slice(11, 16)} – {event.end_at.slice(11, 16)}
          {event.span_days > 1 ? ` · ${event.span_days}天` : ""}
          {event.all_day ? " · 全天" : ""}
        </span>
      </div>
      {event.location ? (
        <div className="cal-quickcard-row">
          <span className="cal-quickcard-k">地点</span>
          <span className="cal-quickcard-v">{event.location}</span>
        </div>
      ) : null}
      {event.note ? (
        <div className="cal-quickcard-row">
          <span className="cal-quickcard-k">备注</span>
          <span className="cal-quickcard-v">{event.note}</span>
        </div>
      ) : null}

      <div className="cal-quickcard-swatches">
        {EVENT_COLORS.map((c) => (
          <button
            key={c}
            className={"cal-swatch" + (event.color === c ? " active" : "")}
            style={{ background: c }}
            title={c}
            onClick={() => onColor(c)}
          />
        ))}
      </div>

      <div className="cal-quickcard-actions">
        <button onClick={() => onRename(event.title)}>改名</button>
        <button onClick={onFocus}>定位</button>
        <button onClick={onAddChild}>加子块</button>
        <button className="danger" onClick={onDelete}>
          删除
        </button>
      </div>
    </div>
  );
}
