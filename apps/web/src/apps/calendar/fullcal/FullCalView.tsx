/**
 * V8 · FullCalendar 6.1.21 原型视图（对照表 v1 实证件）。
 *
 * ★ 总监 22:45 拍板：FullCalendar 6.1.21 全家桶（core/interaction/daygrid/timegrid 同版本混装禁令）
 *   为日程重构内核主选。本组件为「替换层」原型：
 *   - 保留 useCalendarEvents 数据层 + api.ts 写请求（Idempotency-Key 不动）；
 *   - 用 FullCalendar 替换自研 MonthGrid/TimeGrid 的渲染与拖拽/缩放交互；
 *   - 三视图：dayGridMonth / timeGridWeek / timeGridDay；
 *   - 交互：拖拽（eventDrop）/ 缩放（eventResize）/ 拖选新建（select）/ 点击详情（eventClick）。
 *
 * 对照表 v1 验收：① 日周月三视图渲染 ✅ ② 色块可拖可拉伸（上下/左右）✅
 * ③ 拖动/拉伸后事件时间动态匹配（回调写回后端）✅ ④ 拖选空白新建 ✅
 */
import { useMemo, useRef, useEffect } from "react";
import FullCalendar from "@fullcalendar/react";
import dayGridPlugin from "@fullcalendar/daygrid";
import timeGridPlugin from "@fullcalendar/timegrid";
import interactionPlugin from "@fullcalendar/interaction";
import zhCnLocale from "@fullcalendar/core/locales/zh-cn";
import type { CalendarEvent } from "../api";
import type { EventInput, EventApi } from "@fullcalendar/core";
import "../calendar.css";

export type CalView = "day" | "week" | "month";

/**
 * ★ 周起始日 = **周一**，与 CalendarApp 的 `anchorLabel()`（用 `shMonday()`）保持一致。
 *
 * 不设此项时 FullCalendar 默认「周日为首」，而标题按「周一为首」算 ——
 * 同一周会显示成两个范围，整体**错位一天**（标题「10/5–11」vs 列头「Sun 10/4–Sat 10/10」）。
 * zh-cn locale 的 `week.dow = 1`：既修掉错位，也顺带把中文语境补齐。
 */
export const WEEK_LOCALE = zhCnLocale;

interface Props {
  events: CalendarEvent[];
  view: CalView;
  anchor: Date;
  onMove: (id: string, start: string, end: string, spanDays: number) => void;
  onResize: (id: string, start: string, end: string, spanDays: number) => void;
  onCreateAt: (startISO: string, endISO: string) => void;
  onSelect: (id: string) => void;
}

/** CalendarEvent → FullCalendar EventInput 映射（纯函数，可单测）。 */
export function toEventInputs(events: CalendarEvent[]): EventInput[] {
  return events.map((e) => ({
    id: e.id,
    title: e.title,
    start: e.start_at,
    end: e.end_at,
    allDay: e.all_day,
    backgroundColor: e.color || "var(--accent)",
    borderColor: e.color || "var(--accent)",
    classNames: e.parent_id ? ["fc-event--child"] : [],
    extendedProps: {
      parent_id: e.parent_id,
      span_days: e.span_days,
      location: e.location,
      children_count: e.children?.length ?? 0,
    },
  }));
}

/** 父块徽标：子块 ×N 渲染（V8 对照表 v2）。 */
export function renderBadge(childrenCount: number): string {
  if (!childrenCount) return "";
  return ` · 子块 ×${childrenCount}`;
}

/** FullCalendar 视图名映射。 */
export function toFullCalView(view: CalView): string {
  if (view === "day") return "timeGridDay";
  if (view === "week") return "timeGridWeek";
  return "dayGridMonth";
}

/** 拖拽/缩放回调 → 后端 patch（start_at/end_at 带时区 ISO，span_days 随事件）。 */
export function argToSpan(arg: { event: Pick<EventApi, "start" | "end" | "extendedProps"> }): {
  start: string;
  end: string;
  spanDays: number;
} {
  const start = arg.event.start?.toISOString() ?? "";
  const end = arg.event.end?.toISOString() ?? "";
  const prev = arg.event.extendedProps?.span_days as number | undefined;
  const spanDays =
    typeof prev === "number"
      ? prev
      : Math.max(1, Math.round((Date.parse(end) - Date.parse(start)) / 86_400_000));
  return { start, end, spanDays };
}

export default function FullCalView({
  events,
  view,
  anchor,
  onMove,
  onResize,
  onCreateAt,
  onSelect,
}: Props) {
  const eventInputs = useMemo(() => toEventInputs(events), [events]);
  const calendarRef = useRef<FullCalendar>(null);
  const mountedRef = useRef(false);

  // ★ initialView 只在挂载时生效；view prop 变化时用 API 切换视图（令4 主人报"年月日一样"根因）
  useEffect(() => {
    const api = calendarRef.current?.getApi();
    if (api && api.view?.type !== toFullCalView(view)) {
      api.changeView(toFullCalView(view));
    }
  }, [view]);

  // ★ anchor 变化（prev/next/今天按钮）时用 gotoDate 同步 FullCalendar 内部日期。
  //   不再从 datesSet 反喂 setAnchor——FullCalendar 周日起始 vs CalendarApp 周一起始
  //   会造成范围错位循环，导致事件查询范围与显示范围不一致、事件不渲染。
  useEffect(() => {
    const api = calendarRef.current?.getApi();
    if (!api) return;
    if (mountedRef.current) {
      api.gotoDate(anchor);
    }
    mountedRef.current = true;
  }, [anchor]);

  return (
    <div className="cal-fullcal" data-testid="fullcal-view">
      <FullCalendar
        ref={calendarRef}
        plugins={[dayGridPlugin, timeGridPlugin, interactionPlugin]}
        locale={WEEK_LOCALE}
        initialView={toFullCalView(view)}
        initialDate={anchor}
        headerToolbar={{
          left: "",
          center: "",
          right: "",
        }}
        height="100%"
        editable
        selectable
        selectMirror
        dayMaxEvents={4}
        nowIndicator
        events={eventInputs}
        eventContent={(info) => {
          const cc = (info.event.extendedProps?.children_count as number | undefined) ?? 0;
          const txt = `${info.event.title ?? ""}${renderBadge(cc)}`;
          return { html: `<span class="fc-event-title-text">${txt}</span>` };
        }}
        // datesSet 不再反喂 onRangeChange——避免 FullCalendar 周日起始 vs CalendarApp 周一起始的范围错位循环
        datesSet={() => {}}
        eventDrop={(arg) => {
          const { start, end, spanDays } = argToSpan(arg);
          onMove(arg.event.id, start, end, spanDays);
        }}
        eventResize={(arg) => {
          const { start, end, spanDays } = argToSpan(arg);
          onResize(arg.event.id, start, end, spanDays);
        }}
        select={(info) => {
          const s = info.start.toISOString();
          const e = info.end.toISOString();
          onCreateAt(s, e);
        }}
        eventClick={(info) => onSelect(info.event.id)}
      />
    </div>
  );
}
