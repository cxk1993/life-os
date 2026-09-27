/**
 * 课程表数据请求层。
 * 鉴权 / trace_id / RFC7807 解析由 @/shared/api/client 统一处理。
 */
import { api } from "@/shared/api/client";

export interface CourseItem {
  id: string;
  name: string;
  teacher: string | null;
  location: string | null;
  /** 0=周一 … 6=周日 */
  weekday: number;
  start_section: number | null;
  end_section: number | null;
  /** HH:MM */
  start_time: string | null;
  end_time: string | null;
  /** 周次表达式：1-16 / 1,3,5-16 / 2-16双；空=每周 */
  weeks: string | null;
  /** YYYY-MM-DD */
  term_start: string | null;
  note: string | null;
  enabled: boolean;
  sort: number;
  created_at: string;
  updated_at: string;
}

export interface DayColumn {
  weekday: number;
  label: string;
  items: CourseItem[];
}

export interface WeekGrid {
  days: DayColumn[];
  term_start: string | null;
  term_week: number | null;
  /** 纵轴节次列表（如 [1..12]）。 */
  sections: number[];
  /** 今天星期几（0=周一），高亮列用。 */
  today_weekday: number;
}

export interface CourseCreate {
  name: string;
  teacher?: string | null;
  location?: string | null;
  weekday?: number;
  start_section?: number | null;
  end_section?: number | null;
  start_time?: string | null;
  end_time?: string | null;
  weeks?: string | null;
  term_start?: string | null;
  note?: string | null;
  enabled?: boolean;
  sort?: number;
}

export type CoursePatch = Partial<CourseCreate>;

const BASE = "/api/v1/course";

export const WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"] as const;

export const courseApi = {
  list: (params?: { weekday?: number; enabled_only?: boolean }) => {
    const q = new URLSearchParams();
    if (params?.weekday !== undefined) q.set("weekday", String(params.weekday));
    if (params?.enabled_only) q.set("enabled_only", "true");
    const qs = q.toString();
    return api.get<CourseItem[]>(`${BASE}/items${qs ? `?${qs}` : ""}`);
  },
  week: (params?: { date?: string; term_start?: string }) => {
    const q = new URLSearchParams();
    if (params?.date) q.set("date", params.date);
    if (params?.term_start) q.set("term_start", params.term_start);
    const qs = q.toString();
    return api.get<WeekGrid>(`${BASE}/week${qs ? `?${qs}` : ""}`);
  },
  create: (body: CourseCreate) => api.post<CourseItem>(`${BASE}/items`, body),
  update: (id: string, body: CoursePatch) => api.patch<CourseItem>(`${BASE}/items/${id}`, body),
  remove: (id: string) => api.delete<void>(`${BASE}/items/${id}`),
  /** 学期设置：读 / 写（写空串 = 清除）。 */
  getTerm: () => api.get<{ term_start: string | null }>(`${BASE}/term`),
  setTerm: (term_start: string) =>
    api.put<{ term_start: string | null }>(`${BASE}/term`, { term_start }),
};

/** 本地日期串 YYYY-MM-DD。 */
export function localDay(d = new Date()): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/** 该日期所在周的周一（YYYY-MM-DD）。 */
export function mondayOf(d = new Date()): string {
  const x = new Date(d);
  const wd = (x.getDay() + 6) % 7; // 0=周一
  x.setDate(x.getDate() - wd);
  return localDay(x);
}
