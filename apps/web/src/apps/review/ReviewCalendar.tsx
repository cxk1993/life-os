/**
 * ★ 复盘日历视图（astrbot 下场 · 主人令「最好用日历的形式展示，这样我就可以想看哪天就看哪天」）
 *
 * 设计：
 * - 月视图（7 列），有日报的日期高亮可点，无日报的置灰；
 * - 点某天 → onSelect(date) → 上层加载那天的日报（含 AI 分析 / 批注）；
 * - 月份可前后翻；「今天」有独立标记；
 * - 只依赖设计令牌 var(--xxx)，不写死颜色（与 review.css 同风格）。
 */
import { useMemo, useState } from "react";

interface Props {
  /** 有日报的日期集合（ISO yyyy-mm-dd） */
  dates: string[];
  /** 当前选中日期 */
  activeDate: string | null;
  /** 点选某天 */
  onSelect: (date: string) => void;
}

const WEEK = ["一", "二", "三", "四", "五", "六", "日"];

function iso(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function todayIso(): string {
  return iso(new Date());
}

export default function ReviewCalendar({ dates, activeDate, onSelect }: Props) {
  const dateSet = useMemo(() => new Set(dates), [dates]);
  // 以「选中日 / 最近有日报日 / 今天」为锚点决定初始月份
  const anchor = activeDate ?? dates[0] ?? todayIso();
  const [ym, setYm] = useState(() => anchor.slice(0, 7)); // yyyy-mm

  const [year, month] = ym.split("-").map((v) => parseInt(v, 10));

  // 当月网格：从周一补齐到周日
  const cells = useMemo(() => {
    const first = new Date(year, month - 1, 1);
    // JS getDay(): 0=周日；转成周一为首列
    const lead = (first.getDay() + 6) % 7;
    const daysInMonth = new Date(year, month, 0).getDate();
    const out: Array<{ iso: string | null; day: number | null }> = [];
    for (let i = 0; i < lead; i += 1) out.push({ iso: null, day: null });
    for (let d = 1; d <= daysInMonth; d += 1) {
      out.push({ iso: iso(new Date(year, month - 1, d)), day: d });
    }
    while (out.length % 7 !== 0) out.push({ iso: null, day: null });
    return out;
  }, [year, month]);

  const shift = (delta: number) => {
    const d = new Date(year, month - 1 + delta, 1);
    setYm(iso(d).slice(0, 7));
  };

  const today = todayIso();
  const monthLabel = `${year} 年 ${month} 月`;

  return (
    <div className="review-cal" aria-label="日报日历">
      <div className="review-cal__head">
        <button type="button" className="btn" aria-label="上一月" onClick={() => shift(-1)}>
          ‹
        </button>
        <span className="review-cal__label">{monthLabel}</span>
        <button type="button" className="btn" aria-label="下一月" onClick={() => shift(1)}>
          ›
        </button>
      </div>
      <div className="review-cal__week">
        {WEEK.map((w) => (
          <span key={w} className="review-cal__wk">
            {w}
          </span>
        ))}
      </div>
      <div className="review-cal__grid">
        {cells.map((c, i) => {
          if (!c.iso || c.day === null) {
            return <span key={`e${i}`} className="review-cal__cell review-cal__cell--empty" />;
          }
          const has = dateSet.has(c.iso);
          const isActive = c.iso === activeDate;
          const isToday = c.iso === today;
          const cls = [
            "review-cal__cell",
            has ? "review-cal__cell--has" : "",
            isActive ? "review-cal__cell--active" : "",
            isToday ? "review-cal__cell--today" : "",
          ]
            .filter(Boolean)
            .join(" ");
          return (
            <button
              key={c.iso}
              type="button"
              className={cls}
              disabled={!has}
              title={has ? `${c.iso}（有日报）` : `${c.iso}（无日报）`}
              aria-label={has ? `${c.iso} 有日报` : `${c.iso} 无日报`}
              onClick={() => has && onSelect(c.iso as string)}
            >
              {c.day}
            </button>
          );
        })}
      </div>
      <div className="review-cal__legend">
        <span className="review-cal__dot review-cal__dot--has" /> 有日报
        <span className="review-cal__dot review-cal__dot--today" /> 今天
      </div>
    </div>
  );
}
