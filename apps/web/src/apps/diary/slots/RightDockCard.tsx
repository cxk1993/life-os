/**
 * U3 右栏 · 「日历」融合卡（2026-09-27 · 主人「右栏也更新一下」）
 *
 * 主人三条反馈的落地：
 *   ① 「日程」+「日记 · 复盘」两张迷你日历**上下重复** → **合并成一张**；
 *   ② 融合日历的日期格**点不开复盘**（原先格子是纯 `<span>`，根本没绑点击）
 *      → 现在每格可点，点开即看当天全部（日程 / 待办 / 日记 / 复盘），
 *        并可从每段标题**直达**对应窗口；
 *   ③ 四色点阵一眼看清哪天有安排 —— 日程 ● / 待办 ● / 日记 ● / 复盘 ●。
 *
 * 数据源走**内核 BFF**，不做四份并发请求、不 import 别的插件（ADR-0002）：
 *   GET /api/v1/dashboard/day-dots?from=&to=   区间打点（月视图）
 *   GET /api/v1/dashboard/day-peek?date=       单日聚合（选中日）
 * 两个端点都是内核提供的只读聚合，本卡只读不写。
 */
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { api, ApiError } from "@/shared/api/client";
import { useDesktopStore } from "../../../kernel/store";

/** 区间打点：{ "2026-09-27": ["calendar","todo","diary","review"] } */
type DayDots = Record<string, string[]>;

interface PeekListItem {
  id?: string;
  title?: string;
  text?: string;
  start?: string;
  done?: boolean;
}

interface DayPeek {
  date?: string;
  marks?: Record<string, number>;
  dots?: Record<string, boolean>;
  list?: Record<string, PeekListItem[]>;
}

/** 四源（与内核 U2 月历同款，顺序即点阵顺序）。 */
const SOURCES = [
  { key: "calendar", label: "日程", icon: "历" },
  { key: "todo", label: "待办", icon: "待" },
  { key: "diary", label: "日记", icon: "日" },
  { key: "review", label: "复盘", icon: "复" },
] as const;

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

function iso(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export default function RightDockCard() {
  const openWindow = useDesktopStore((s) => s.openWindow);
  const today = useMemo(() => iso(new Date()), []);
  const [view, setView] = useState(() => {
    const d = new Date();
    return { y: d.getFullYear(), m: d.getMonth() };
  });
  const [selected, setSelected] = useState<string>(today);

  const { y, m } = view;
  const monthKey = `${y}-${pad(m + 1)}`;
  const firstIso = `${monthKey}-01`;
  const lastIso = `${monthKey}-${pad(new Date(y, m + 1, 0).getDate())}`;

  // 区间打点（月视图）；点某天不重新拉打点，只拉当天聚合。
  const dotsQ = useQuery({
    queryKey: ["dock-fuse", "dots", firstIso, lastIso],
    queryFn: () => api.get<DayDots>(`/api/v1/dashboard/day-dots?from=${firstIso}&to=${lastIso}`),
    retry: 1,
    refetchOnWindowFocus: false,
  });

  // 选中日聚合（点格子才有内容 —— 这就是原先点不开的那半边）。
  const peekQ = useQuery({
    queryKey: ["dock-fuse", "peek", selected],
    queryFn: () => api.get<DayPeek>(`/api/v1/dashboard/day-peek?date=${selected}`),
    retry: 1,
    refetchOnWindowFocus: false,
  });

  const firstDow = (new Date(y, m, 1).getDay() + 6) % 7; // 周一为首列
  const daysInMonth = new Date(y, m + 1, 0).getDate();
  const cells: (number | null)[] = [
    ...Array.from({ length: firstDow }, () => null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ];

  const shift = (delta: number) => {
    const d = new Date(y, m + delta, 1);
    setView({ y: d.getFullYear(), m: d.getMonth() });
  };

  const dots = dotsQ.data ?? {};
  const peek = peekQ.data;
  const list = peek?.list ?? {};

  return (
    <div className="dock-card" data-testid="diary-review-right-card">
      <div className="dock-card__head" style={{ cursor: "default" }}>
        <span>日历</span>
        <span className="dock-card__sub">日程 · 待办 · 日记 · 复盘</span>
      </div>

      <div className="dock-fuse__nav">
        <button type="button" aria-label="上个月" onClick={() => shift(-1)}>
          ‹
        </button>
        <span className="dock-fuse__title">
          {y} 年 {m + 1} 月
        </span>
        <button type="button" aria-label="下个月" onClick={() => shift(1)}>
          ›
        </button>
        <button
          type="button"
          className="dock-fuse__today"
          aria-label="回到今天"
          onClick={() => {
            const d = new Date();
            setView({ y: d.getFullYear(), m: d.getMonth() });
            setSelected(iso(d));
          }}
        >
          今
        </button>
      </div>

      {dotsQ.isLoading ? (
        <div className="dock-card__empty">…</div>
      ) : dotsQ.isError ? (
        <div className="dock-card__empty" data-testid="dock-fuse-err">
          {dotsQ.error instanceof ApiError && dotsQ.error.status === 401 ? "未登录" : "暂时不可用"}
        </div>
      ) : (
        <div className="dock-fuse__grid" aria-label="本月点阵（可点选日期）">
          {cells.map((d, i) => {
            if (d === null) return <span key={i} className="dock-fuse__cell is-empty" />;
            const ds = `${monthKey}-${pad(d)}`;
            const ds_marks = dots[ds] ?? [];
            const isToday = ds === today;
            const isSel = ds === selected;
            return (
              <button
                type="button"
                key={i}
                data-testid={`dock-fuse-day-${ds}`}
                className={`dock-fuse__cell${isToday ? " is-today" : ""}${isSel ? " is-selected" : ""}`}
                title={ds_marks.length ? `${ds} · ${ds_marks.length} 项` : ds}
                onClick={() => setSelected(ds)}
              >
                {d}
                {ds_marks.length > 0 ? (
                  <span className="dock-fuse__dots" aria-hidden="true">
                    {SOURCES.map((s) => (
                      <i
                        key={s.key}
                        className={`dock-fuse__dot dock-fuse__dot--${s.key}${
                          ds_marks.includes(s.key) ? " is-on" : ""
                        }`}
                      />
                    ))}
                  </span>
                ) : null}
              </button>
            );
          })}
        </div>
      )}

      <div className="dock-fuse__legend">
        {SOURCES.map((s) => (
          <span key={s.key} className="dock-fuse__legend-item">
            <i className={`dock-fuse__dot dock-fuse__dot--${s.key} is-on`} aria-hidden="true" />
            {s.label}
          </span>
        ))}
      </div>

      <div className="dock-fuse__peek" data-testid="dock-fuse-peek">
        <div className="dock-fuse__peek-title">{selected}</div>
        {peekQ.isLoading ? (
          <div className="dock-card__empty">…</div>
        ) : peekQ.isError ? (
          <div className="dock-card__empty">当日数据取不到</div>
        ) : (
          SOURCES.map((s) => {
            const items = list[s.key] ?? [];
            return (
              <div key={s.key} className="dock-fuse__sec">
                <button
                  type="button"
                  className="dock-fuse__sec-head"
                  onClick={() => openWindow(s.key)}
                  aria-label={`打开${s.label}`}
                >
                  <span className="dock-fuse__sec-icon">{s.icon}</span>
                  {s.label}
                  {items.length > 0 ? <span className="dock-fuse__cnt">{items.length}</span> : null}
                  <span className="dock-fuse__go">打开 ›</span>
                </button>
                {items.length === 0 ? null : (
                  <ul className="dock-fuse__list">
                    {items.slice(0, 3).map((it, k) => (
                      <li key={k} className="dock-fuse__item">
                        {it.start ? <span className="dock-fuse__time">{it.start.slice(11, 16)}</span> : null}
                        <span className="dock-fuse__txt">{it.title ?? it.text ?? ""}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
