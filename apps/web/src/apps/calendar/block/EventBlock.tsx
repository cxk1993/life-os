/**
 * 日程色块（单段）：负责渲染、拖动、下/右缘拉伸、选中、QuickCard、就地改名。
 * 一个跨天事件会被 TimeGrid 拆成多段，每段是一个 EventBlock。
 */

import { useEffect, useRef, useState } from "react";
import type { CalendarEvent } from "../api";
import { useBlockDrag, type DragDelta } from "./useBlockDrag";
import { useBlockResize, type ResizeMode, type ResizeDelta } from "./useBlockResize";
import {
  applyMove,
  applyResizeBottom,
  applyResizeRight,
  clampChild,
  addDays,
  startOfDay,
  HOUR_MS,
} from "../lib/time";
import { QuickCard } from "../inspector/QuickCard";

export interface BlockCommit {
  start: string;
  end: string;
  spanDays: number;
}

interface Props {
  event: CalendarEvent;
  segStart: Date;
  segEnd: Date;
  dayIndex: number;
  dayWidth: number;
  hourHeight: number;
  weekStart: Date;
  weekDays: number;
  isChild: boolean;
  selected: boolean;
  overlap: boolean;
  parentEvent?: CalendarEvent | null;
  onSelect: (id: string) => void;
  onMove: (start: string, end: string, spanDays: number) => void;
  onResize: (mode: ResizeMode, start: string, end: string, spanDays: number) => void;
  onRename: (title: string) => void;
  onColor: (color: string) => void;
  onFocus: () => void;
  onAddChild: () => void;
  onDelete: () => void;
}

function pad(n: number): string {
  return String(n).padStart(2, "0");
}
function formatHM(d: Date): string {
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function EventBlock(props: Props) {
  const {
    event,
    segStart,
    segEnd,
    dayIndex,
    dayWidth,
    hourHeight,
    weekStart,
    weekDays,
    isChild,
    selected,
    overlap,
    parentEvent,
  } = props;

  const [renaming, setRenaming] = useState(false);
  const [quickOpen, setQuickOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const columnStart = addDays(startOfDay(weekStart), dayIndex);
  const top = ((segStart.getTime() - columnStart.getTime()) / HOUR_MS) * hourHeight;
  const height = ((segEnd.getTime() - segStart.getTime()) / HOUR_MS) * hourHeight;
  const left = isChild ? dayWidth * 0.06 : 2;
  const width = dayWidth - (isChild ? dayWidth * 0.12 : 4);

  const bounds = { weekStart, weekDays };

  const handleMove = (d: DragDelta) => {
    if (d.dDays === 0 && d.dHours === 0) return; // 纯点击，不提交
    const s0 = new Date(event.start_at);
    const e0 = new Date(event.end_at);
    const m = applyMove(s0, e0, d.dDays, d.dHours, bounds);
    let s = m.start;
    let e = m.end;
    if (parentEvent) {
      const c = clampChild(new Date(parentEvent.start_at), new Date(parentEvent.end_at), s, e);
      s = c.start;
      e = c.end;
    }
    props.onMove(s.toISOString(), e.toISOString(), m.spanDays);
  };

  const handleResize = (mode: ResizeMode, delta: ResizeDelta) => {
    const s0 = new Date(event.start_at);
    const e0 = new Date(event.end_at);
    // 两个分支统一携带 spanDays：右缘拉伸产生新跨度；下缘拉伸不改变跨天数。
    const resized =
      mode === "bottom"
        ? { ...applyResizeBottom(s0, e0, delta.dHours), spanDays: event.span_days }
        : applyResizeRight(s0, e0, delta.dDays, bounds);
    let s = resized.start;
    let e = resized.end;
    if (parentEvent) {
      const c = clampChild(new Date(parentEvent.start_at), new Date(parentEvent.end_at), s, e);
      s = c.start;
      e = c.end;
    }
    props.onResize(mode, s.toISOString(), e.toISOString(), resized.spanDays);
  };

  const drag = useBlockDrag({ hourHeight, dayWidth, onCommit: handleMove });
  const resize = useBlockResize({ hourHeight, dayWidth, onCommit: handleResize });

  useEffect(() => {
    if (renaming) inputRef.current?.focus();
  }, [renaming]);

  const cls = [
    "cal-block",
    isChild ? "child" : "",
    selected ? "selected" : "",
    overlap ? "overlap" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div
      className={cls}
      style={{
        top,
        height: Math.max(height, 18),
        left,
        width,
        // 用设计令牌承载颜色，背景/边框由 CSS 用 color-mix 派生子色
        ["--ev-color" as string]: event.color || "var(--accent)",
      }}
      onPointerDown={(e) => {
        // 仅左键、且不是拉伸把手时启动移动
        if (e.button === 0) drag.start(e);
      }}
      onClick={(e) => {
        e.stopPropagation();
        props.onSelect(event.id);
        setQuickOpen(true);
      }}
      onDoubleClick={(e) => {
        e.stopPropagation();
        setRenaming(true);
        setQuickOpen(false);
      }}
    >
      <div className="cal-block-bar" />
      <div className="cal-block-body">
        {renaming ? (
          <input
            ref={inputRef}
            className="cal-block-rename"
            defaultValue={event.title}
            onPointerDown={(e) => e.stopPropagation()}
            onBlur={(e) => {
              props.onRename(e.target.value || event.title);
              setRenaming(false);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") (e.target as HTMLInputElement).blur();
              if (e.key === "Escape") setRenaming(false);
            }}
          />
        ) : (
          <span className="cal-block-title" title={event.title}>
            {event.title}
          </span>
        )}
        <span className="cal-block-time">
          {formatHM(segStart)}–{formatHM(segEnd)}
        </span>
        {event.children?.length ? (
          <span className="cal-block-badge">{event.children.length}</span>
        ) : null}
      </div>

      {/* 拉伸把手 */}
      <div
        className="cal-resize cal-resize-bottom"
        onPointerDown={(e) => resize.start("bottom")(e)}
      />
      <div
        className="cal-resize cal-resize-right"
        onPointerDown={(e) => resize.start("right")(e)}
      />

      {quickOpen ? (
        <QuickCard
          event={event}
          onClose={() => setQuickOpen(false)}
          onRename={(t) => {
            props.onRename(t);
            setQuickOpen(false);
          }}
          onColor={props.onColor}
          onFocus={() => {
            props.onFocus();
            setQuickOpen(false);
          }}
          onAddChild={() => {
            props.onAddChild();
            setQuickOpen(false);
          }}
          onDelete={() => {
            props.onDelete();
            setQuickOpen(false);
          }}
        />
      ) : null}
    </div>
  );
}
