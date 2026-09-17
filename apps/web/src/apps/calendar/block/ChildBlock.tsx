/**
 * 嵌套子块：复用 EventBlock，仅以 child 态渲染（更深色系 + 缩进），
 * 并带父块引用以便拖动/缩放时钳制在父块内（见 EventBlock 的 clampChild 调用）。
 */

import { EventBlock, type BlockCommit } from "./EventBlock";
import type { CalendarEvent } from "../api";
import type { ResizeMode } from "./useBlockResize";

interface Props {
  event: CalendarEvent;
  segStart: Date;
  segEnd: Date;
  dayIndex: number;
  dayWidth: number;
  hourHeight: number;
  weekStart: Date;
  weekDays: number;
  selected: boolean;
  overlap: boolean;
  parentEvent: CalendarEvent;
  onSelect: (id: string) => void;
  onMove: (start: string, end: string, spanDays: number) => void;
  onResize: (mode: ResizeMode, start: string, end: string, spanDays: number) => void;
  onRename: (title: string) => void;
  onColor: (color: string) => void;
  onFocus: () => void;
  onAddChild: () => void;
  onDelete: () => void;
}

export function ChildBlock(props: Props) {
  return <EventBlock {...props} isChild parentEvent={props.parentEvent} />;
}

export type { BlockCommit };
