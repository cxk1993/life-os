/**
 * ★ 课程表（2026-09-27 · 主人「日程待办窗口里加一个分页课程表」）
 *
 * 需求：大学的课表本身（哪门课、周几、第几节、在哪、谁上）需要一个专门视图，
 *       与「学业」（作业 deadline）分工：**课程表看「什么时候上课」，学业看「作业什么时候交」**。
 *
 * 设计：
 *   - 主视图 = **节次 × 星期 网格**（行=节次，列=周一…周日）—— 主人「节次做成纵轴」；
 *   - **学期起始日**可设（toolbar「学期设置」）→ 显示「第 N 教学周」，weeks 才有意义；
 *   - 点卡片 → 编辑；工具条 → 新建；表单一处复用（新建 / 编辑同一张）；
 *   - 「保留推送能力」：后端 `course/remind_scheduler.py` 扫到即将上课 →
 *     发 `course.session.due` → push 插件 broadcast（上课前 30 分钟提醒）；
 *   - 挂载点：schedule 容器的第 4 页（[日程表][待办][学业][课程表]）。
 */
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { usePluginEvent } from "@/shared/api/events";
import { api } from "@/shared/api/client";
import { Modal } from "@/shared/components/Modal";
import { EmptyState } from "@/shared/components/EmptyState";
import { Skeleton } from "@/shared/components/Skeleton";

import { WEEKDAYS, courseApi, localDay, mondayOf } from "./api";
import type { CourseCreate, CourseItem } from "./api";
import "./course.css";

const EMPTY: CourseCreate = {
  name: "",
  teacher: "",
  location: "",
  weekday: 0,
  start_section: null,
  end_section: null,
  start_time: "",
  end_time: "",
  weeks: "",
  note: "",
  enabled: true,
};

export default function CourseApp() {
  const qc = useQueryClient();
  const [editing, setEditing] = useState<CourseItem | null>(null);
  const [creating, setCreating] = useState(false);
  const [draft, setDraft] = useState<CourseCreate>(EMPTY);
  const [termOpen, setTermOpen] = useState(false);
  const [termDraft, setTermDraft] = useState("");

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["course", "week"],
    queryFn: () => courseApi.week(),
  });

  const schedQ = useQuery({
    queryKey: ["course", "scheduler"],
    queryFn: () =>
      api.get<{ enabled: boolean; running: boolean; lead_minutes: number }>(
        "/api/v1/course/due/scheduler",
      ),
    retry: 0,
  });

  // 课表变更 → 失效本地缓存（SSE 事件）
  usePluginEvent("course.item.created", () => qc.invalidateQueries({ queryKey: ["course"] }));
  usePluginEvent("course.item.updated", () => qc.invalidateQueries({ queryKey: ["course"] }));
  usePluginEvent("course.item.deleted", () => qc.invalidateQueries({ queryKey: ["course"] }));

  const saveMut = useMutation({
    mutationFn: (body: CourseCreate) =>
      editing ? courseApi.update(editing.id, body) : courseApi.create(body),
    onSuccess: () => {
      setEditing(null);
      setCreating(false);
      setDraft(EMPTY);
      qc.invalidateQueries({ queryKey: ["course"] });
    },
  });

  const delMut = useMutation({
    mutationFn: (id: string) => courseApi.remove(id),
    onSuccess: () => {
      setEditing(null);
      setCreating(false);
      qc.invalidateQueries({ queryKey: ["course"] });
    },
  });

  const termMut = useMutation({
    mutationFn: (v: string) => courseApi.setTerm(v),
    onSuccess: () => {
      setTermOpen(false);
      qc.invalidateQueries({ queryKey: ["course"] });
    },
  });

  const monday = mondayOf();
  const days = useMemo(() => data?.days ?? [], [data]);
  const sections = useMemo(() => data?.sections ?? [], [data]);
  const todayWeekday = data?.today_weekday ?? -1;

  /** 该列对应的真实日期（周一 + offset）。 */
  const dateOf = (weekday: number) => {
    const d = new Date(`${monday}T00:00:00`);
    d.setDate(d.getDate() + weekday);
    return localDay(d);
  };

  const openNew = (weekday?: number, section?: number) => {
    setEditing(null);
    // 默认星期 = 今天（JS getDay 0=周日 → 本系统 0=周一）
    const jsDay = new Date().getDay();
    const fallback = jsDay === 0 ? 6 : jsDay - 1;
    setDraft({
      ...EMPTY,
      weekday: weekday ?? fallback,
      start_section: section ?? null,
      end_section: section ?? null,
    });
    setCreating(true);
  };

  const openEdit = (item: CourseItem) => {
    setEditing(item);
    setDraft({
      name: item.name,
      teacher: item.teacher ?? "",
      location: item.location ?? "",
      weekday: item.weekday,
      start_section: item.start_section,
      end_section: item.end_section,
      start_time: item.start_time ?? "",
      end_time: item.end_time ?? "",
      weeks: item.weeks ?? "",
      note: item.note ?? "",
      enabled: item.enabled,
    });
    setCreating(true);
  };

  /** 按节次分桶：section → weekday → items（只按 start_section 定位，跨节在卡片上标注）。 */
  const buckets = useMemo(() => {
    const m: Record<number, Record<number, CourseItem[]>> = {};
    const unscheduled: CourseItem[] = [];
    for (const col of days) {
      for (const it of col.items) {
        if (!it.start_section) {
          unscheduled.push(it);
          continue;
        }
        (m[it.start_section] ??= {})[col.weekday] ??= [];
        m[it.start_section][col.weekday].push(it);
      }
    }
    return { m, unscheduled };
  }, [days]);

  const total = useMemo(() => days.reduce((n, c) => n + c.items.length, 0), [days]);

  const renderCard = (it: CourseItem) => (
    <button
      type="button"
      key={it.id}
      className={`course-card${it.enabled ? "" : " is-off"}`}
      onClick={() => openEdit(it)}
      title={`${it.name}${it.location ? ` @ ${it.location}` : ""}`}
    >
      <span className="course-card__name">{it.name}</span>
      {it.start_time ? (
        <span className="course-card__time">
          {it.start_time}
          {it.end_time ? `–${it.end_time}` : ""}
        </span>
      ) : null}
      {it.location || it.teacher ? (
        <span className="course-card__meta">{[it.location, it.teacher].filter(Boolean).join(" · ")}</span>
      ) : null}
      {it.weeks ? <span className="course-card__weeks">周次 {it.weeks}</span> : null}
    </button>
  );

  return (
    <div className="course-win" data-testid="course-app">
      <div className="course-bar">
        <span className="course-bar__title">课程表</span>
        <span className="course-bar__sub">
          {data?.term_week ? `第 ${data.term_week} 教学周 · ` : ""}
          共 {total} 个课时
          {schedQ.data
            ? schedQ.data.running
              ? ` · 上课前 ${schedQ.data.lead_minutes} 分钟提醒中`
              : " · 上课提醒未开启"
            : ""}
        </span>
        <span className="course-bar__spacer" />
        <button
          type="button"
          className="course-btn"
          onClick={() => {
            setTermDraft(data?.term_start ?? "");
            setTermOpen(true);
          }}
          data-testid="course-term"
        >
          学期设置
        </button>
        <button type="button" className="course-btn" onClick={() => refetch()} aria-label="刷新课表">
          刷新
        </button>
        <button
          type="button"
          className="course-btn course-btn--primary"
          onClick={() => openNew()}
          data-testid="course-add"
        >
          + 加课
        </button>
      </div>

      {isLoading ? (
        <div className="course-grid">
          {[0, 1, 2, 3, 4, 5, 6].map((i) => (
            <Skeleton key={i} height={200} />
          ))}
        </div>
      ) : error ? (
        <EmptyState text="课表加载失败" hint={(error as Error).message} />
      ) : total === 0 ? (
        <EmptyState
          text="还没有课程"
          hint="点右上角「+ 加课」录入：课名、周几、第几节、地点。录完就能在上课前收到提醒。"
        />
      ) : (
        <div className="course-sheet" data-testid="course-grid">
          {/* 表头：角 + 7 天 */}
          <div className="course-hrow">
            <div className="course-hcell course-hcell--corner">节次</div>
            {days.map((col) => {
              const isToday = col.weekday === todayWeekday;
              return (
                <div
                  key={col.weekday}
                  className={`course-hcell${isToday ? " is-today" : ""}`}
                >
                  <span className="course-hcell__name">{col.label}</span>
                  <span className="course-hcell__date">{dateOf(col.weekday).slice(5)}</span>
                </div>
              );
            })}
          </div>

          {/* 正文：行=节次，列=星期 */}
          {sections.map((sec) => (
            <div className="course-row" key={sec} data-testid={`course-sec-${sec}`}>
              <div className="course-sec">{sec}</div>
              {days.map((col) => {
                const items = buckets.m[sec]?.[col.weekday] ?? [];
                return (
                  <div className="course-cell" key={col.weekday}>
                    {items.map(renderCard)}
                    {items.length === 0 ? (
                      <button
                        type="button"
                        className="course-cell__add"
                        aria-label={`给${col.label}第${sec}节加课`}
                        onClick={() => openNew(col.weekday, sec)}
                      >
                        +
                      </button>
                    ) : null}
                  </div>
                );
              })}
            </div>
          ))}

          {/* 未填节次的课（只填了时间）单独一区 */}
          {buckets.unscheduled.length > 0 ? (
            <div className="course-row course-row--extra">
              <div className="course-sec">—</div>
              {days.map((col) => {
                const items = buckets.unscheduled.filter((it) => it.weekday === col.weekday);
                return (
                  <div className="course-cell" key={col.weekday}>
                    {items.map(renderCard)}
                  </div>
                );
              })}
            </div>
          ) : null}
        </div>
      )}

      {/* ── 学期设置 ── */}
      <Modal open={termOpen} title="学期设置" onClose={() => setTermOpen(false)}>
        <form
          className="course-form"
          onSubmit={(e) => {
            e.preventDefault();
            if (termMut.isPending) return;
            termMut.mutate(termDraft.trim());
          }}
        >
          <div className="course-field course-field--wide">
            <label htmlFor="ct-term">第一周周一（填写后显示「第 N 教学周」，周次表达式才有意义）</label>
            <input
              id="ct-term"
              type="date"
              value={termDraft}
              onChange={(e) => setTermDraft(e.target.value)}
              data-testid="course-term-input"
            />
          </div>
          <div className="course-field course-field--wide">
            <span className="course-hint">
              当前：{data?.term_start ? `${data.term_start}（第 ${data.term_week ?? "?"} 教学周）` : "未设置"}
            </span>
          </div>
          {termMut.error ? (
            <div className="course-form__err" role="alert">
              保存失败：{(termMut.error as Error).message}
            </div>
          ) : null}
          <div className="course-actions">
            <button
              type="button"
              className="course-btn"
              onClick={() => termMut.mutate("")}
              disabled={termMut.isPending}
            >
              清除
            </button>
            <button type="button" className="course-btn" onClick={() => setTermOpen(false)}>
              取消
            </button>
            <button type="submit" className="course-btn course-btn--primary" disabled={termMut.isPending}>
              {termMut.isPending ? "保存中…" : "保存"}
            </button>
          </div>
        </form>
      </Modal>

      <Modal
        open={creating}
        title={editing ? `编辑课程 · ${editing.name}` : "加一门课"}
        onClose={() => {
          setCreating(false);
          setEditing(null);
        }}
      >
        <form
          className="course-form"
          onSubmit={(e) => {
            e.preventDefault();
            if (!draft.name.trim() || saveMut.isPending) return;
            saveMut.mutate({
              ...draft,
              name: draft.name.trim(),
              weekday: Number(draft.weekday ?? 0),
              start_section: draft.start_section ? Number(draft.start_section) : null,
              end_section: draft.end_section ? Number(draft.end_section) : null,
            });
          }}
        >
          <div className="course-field">
            <label htmlFor="cf-name">课名 *</label>
            <input
              id="cf-name"
              value={draft.name}
              onChange={(e) => setDraft({ ...draft, name: e.target.value })}
              placeholder="高等数学"
              required
            />
          </div>
          <div className="course-field">
            <label htmlFor="cf-teacher">教师</label>
            <input
              id="cf-teacher"
              value={draft.teacher ?? ""}
              onChange={(e) => setDraft({ ...draft, teacher: e.target.value })}
              placeholder="张老师"
            />
          </div>
          <div className="course-field">
            <label htmlFor="cf-weekday">星期</label>
            <select
              id="cf-weekday"
              value={draft.weekday ?? 0}
              onChange={(e) => setDraft({ ...draft, weekday: Number(e.target.value) })}
            >
              {WEEKDAYS.map((w, i) => (
                <option key={i} value={i}>
                  {w}
                </option>
              ))}
            </select>
          </div>
          <div className="course-field">
            <label htmlFor="cf-location">地点</label>
            <input
              id="cf-location"
              value={draft.location ?? ""}
              onChange={(e) => setDraft({ ...draft, location: e.target.value })}
              placeholder="知新楼 B203"
            />
          </div>
          <div className="course-field">
            <label htmlFor="cf-sec-start">起始节次</label>
            <input
              id="cf-sec-start"
              type="number"
              min={1}
              max={20}
              value={draft.start_section ?? ""}
              onChange={(e) =>
                setDraft({
                  ...draft,
                  start_section: e.target.value ? Number(e.target.value) : null,
                })
              }
              placeholder="1"
            />
          </div>
          <div className="course-field">
            <label htmlFor="cf-sec-end">结束节次</label>
            <input
              id="cf-sec-end"
              type="number"
              min={1}
              max={20}
              value={draft.end_section ?? ""}
              onChange={(e) =>
                setDraft({ ...draft, end_section: e.target.value ? Number(e.target.value) : null })
              }
              placeholder="2"
            />
          </div>
          <div className="course-field">
            <label htmlFor="cf-start">上课时间</label>
            <input
              id="cf-start"
              type="time"
              value={draft.start_time ?? ""}
              onChange={(e) => setDraft({ ...draft, start_time: e.target.value })}
            />
          </div>
          <div className="course-field">
            <label htmlFor="cf-end">下课时间</label>
            <input
              id="cf-end"
              type="time"
              value={draft.end_time ?? ""}
              onChange={(e) => setDraft({ ...draft, end_time: e.target.value })}
            />
          </div>
          <div className="course-field">
            <label htmlFor="cf-weeks">周次（如 1-16 / 1,3,5-16 / 2-16双；空=每周）</label>
            <input
              id="cf-weeks"
              value={draft.weeks ?? ""}
              onChange={(e) => setDraft({ ...draft, weeks: e.target.value })}
              placeholder="留空表示每周都上"
            />
          </div>
          <div className="course-field">
            <label htmlFor="cf-enabled">状态</label>
            <select
              id="cf-enabled"
              value={draft.enabled === false ? "0" : "1"}
              onChange={(e) => setDraft({ ...draft, enabled: e.target.value === "1" })}
            >
              <option value="1">启用（会提醒）</option>
              <option value="0">停课（不提醒）</option>
            </select>
          </div>
          <div className="course-field course-field--wide">
            <label htmlFor="cf-note">备注</label>
            <input
              id="cf-note"
              value={draft.note ?? ""}
              onChange={(e) => setDraft({ ...draft, note: e.target.value })}
              placeholder="可选"
            />
          </div>

          {saveMut.error ? (
            <div className="course-form__err" role="alert">
              保存失败：{(saveMut.error as Error).message}
            </div>
          ) : null}

          <div className="course-actions">
            {editing ? (
              <button
                type="button"
                className="course-btn"
                onClick={() => delMut.mutate(editing.id)}
                disabled={delMut.isPending}
              >
                删除
              </button>
            ) : null}
            <button
              type="button"
              className="course-btn"
              onClick={() => {
                setCreating(false);
                setEditing(null);
              }}
            >
              取消
            </button>
            <button type="submit" className="course-btn course-btn--primary" disabled={saveMut.isPending}>
              {saveMut.isPending ? "保存中…" : "保存"}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
