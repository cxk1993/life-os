import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { ApiError } from "@/shared/api/client";
import { useDesktopStore } from "../../../kernel/store";
import { diaryApi } from "../api";
import { reviewApi } from "../../review/api";

/** U3 右栏 · 复盘与日记融合小日历。 */
export default function RightDockCard() {
  const openWindow = useDesktopStore((s) => s.openWindow);
  const now = new Date();
  const y = now.getFullYear();
  const m = now.getMonth() + 1;
  const today = `${y}-${String(m).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;

  const diaryQ = useQuery({
    queryKey: ["diary", "right-month", y, m],
    queryFn: async () => {
      try {
        return await diaryApi.month(y, m);
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) return null;
        throw e;
      }
    },
    retry: 1,
    refetchOnWindowFocus: false,
  });

  const todayQ = useQuery({
    queryKey: ["diary", "right-today"],
    queryFn: () => diaryApi.today(),
    retry: 1,
    refetchOnWindowFocus: false,
  });

  const reviewQ = useQuery({
    queryKey: ["review", "right-days"],
    queryFn: async () => {
      try {
        return await reviewApi.days({ size: 5 });
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) return null;
        throw e;
      }
    },
    retry: 1,
    refetchOnWindowFocus: false,
  });

  const diaryDays = useMemo(() => new Set(diaryQ.data?.days ?? []), [diaryQ.data]);
  const reviewDates = useMemo(() => {
    const items = reviewQ.data?.items ?? [];
    return new Set(
      items.map((it) => String((it as { date?: string }).date ?? "").slice(0, 10)),
    );
  }, [reviewQ.data]);

  const firstDow = (new Date(y, now.getMonth(), 1).getDay() + 6) % 7;
  const daysInMonth = new Date(y, m, 0).getDate();
  const cells: (number | null)[] = [
    ...Array.from({ length: firstDow }, () => null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ];

  const todayDiary = todayQ.data;
  const recentReviews = (reviewQ.data?.items ?? []).slice(0, 3);

  return (
    <div className="dock-card" data-testid="diary-review-right-card">
      <div className="dock-card__head" style={{ cursor: "default" }}>
        <span>日记 · 复盘</span>
        <span className="dock-card__sub">融合小日历</span>
      </div>
      {diaryQ.isLoading && !diaryQ.data ? (
        <div className="dock-card__empty">…</div>
      ) : (
        <div>
          <div className="dock-mini-cal" aria-label="日记复盘点阵">
            {cells.map((d, i) => {
              if (d === null) return <span key={i} className="dock-mini-cal__cell is-empty" />;
              const ds = `${y}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
              const isToday = ds === today;
              const hasD = diaryDays.has(ds);
              const hasR = reviewDates.has(ds);
              const cls =
                "dock-mini-cal__cell" +
                (isToday ? " is-today" : "") +
                (hasD ? " has-mark" : "") +
                (hasR ? " has-mark2" : "");
              return (
                <span key={i} className={cls} title={ds}>
                  {d}
                </span>
              );
            })}
          </div>
          <ul className="dock-card__list">
            <li className="dock-card__item">
              <button type="button" className="dock-card__txt" onClick={() => openWindow("diary")}>
                今日日记：{todayDiary?.exists ? "已写" : "未写"}
              </button>
            </li>
            {recentReviews.map((it, i) => (
              <li key={i} className="dock-card__item">
                <button
                  type="button"
                  className="dock-card__txt"
                  onClick={() => openWindow("review")}
                >
                  复盘 · {String((it as { date?: string }).date ?? "").slice(0, 10)}
                </button>
              </li>
            ))}
          </ul>
          <div className="dock-card__empty">点：日记 ● · 复盘 ◆</div>
        </div>
      )}
    </div>
  );
}
