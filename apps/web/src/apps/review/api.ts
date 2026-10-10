/** 复盘数据请求层。鉴权 / RFC7807 由 @/shared/api/client 统一处理。 */
import { api } from "@/shared/api/client";

export type NamedRow = {
  name: string;
  seconds: number;
  duration_text: string;
};

export type HourlyRow = {
  hour: number;
  seconds: number;
  duration_text: string;
};

export type SourceInfo = {
  mode: string;
  path: string;
  bridge: boolean;
  bridge_online: boolean | null;
  upstream_online: boolean;
  upstream_version: string | null;
  last_sync_at: string | null;
  message: string;
};

export type ReviewNote = {
  id: string;
  date: string;
  content_md: string;
  created_at: string;
};

export type DayListItem = {
  date: string;
  is_empty: boolean;
  total_seconds: number;
  category_count: number;
  app_count: number;
  has_ai: boolean;
  has_raw: boolean;
  raw_path: string;
  top_categories: NamedRow[];
  synced_at: string | null;
};

export type DaysOut = {
  items: DayListItem[];
  total: number;
  page: number;
  size: number;
  has_more: boolean;
};

export type DayDetail = {
  date: string;
  is_empty: boolean;
  empty_hint: string;
  categories: NamedRow[];
  apps: NamedRow[];
  domains: NamedRow[];
  hourly: HourlyRow[];
  ai_analysis_md: string;
  total_seconds: number;
  raw_path: string;
  has_raw: boolean;
  synced_at: string | null;
  notes: ReviewNote[];
  source: SourceInfo | null;
};

export type TrendPoint = {
  date: string;
  total_seconds: number;
  values: Record<string, number>;
};

export type TrendOut = {
  metric: string;
  days: number;
  points: TrendPoint[];
  labels: string[];
  conclusion: string;
};

export type WeeklyOut = {
  date: string;
  available: boolean;
  offline_hint: string;
  week_start: string | null;
  week_end: string | null;
  total_seconds: number;
  days: Array<Record<string, unknown>>;
  summary: string;
  source: string;
  cached: boolean;
};

export type RawOut = {
  date: string;
  markdown: string;
  raw_path: string;
  found: boolean;
};

export type IngestOut = {
  date: string;
  id: string;
  raw_path: string;
  is_empty: boolean;
  category_count: number;
  app_count: number;
  has_ai: boolean;
  has_raw: boolean;
  synced_at: string | null;
  mode: string;
  path: string;
  event: string;
};

export type HealthOut = {
  ok: boolean;
  upstream_mode: string;
  path: string;
  bridge: boolean;
  version: string | null;
  status: string | null;
  message: string;
};

const BASE = "/api/v1/review";

export function formatSeconds(sec: number): string {
  const s = Math.max(0, Math.floor(sec || 0));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const r = s % 60;
  if (h > 0) return `${h}小时${m}分${r}秒`;
  if (m > 0) return `${m}分${r}秒`;
  return `${r}秒`;
}

export const reviewApi = {
  health: () => api.get<HealthOut>(`${BASE}/health`),
  source: () => api.get<SourceInfo>(`${BASE}/source`),
  days: (params?: { from?: string; to?: string; page?: number; size?: number }) => {
    const q = new URLSearchParams();
    if (params?.from) q.set("from", params.from);
    if (params?.to) q.set("to", params.to);
    q.set("page", String(params?.page ?? 1));
    q.set("size", String(params?.size ?? 20));
    return api.get<DaysOut>(`${BASE}/days?${q.toString()}`);
  },
  day: (date: string) => api.get<DayDetail>(`${BASE}/day?date=${encodeURIComponent(date)}`),
  trend: (metric = "total", days = 7) =>
    api.get<TrendOut>(`${BASE}/trend?metric=${metric}&days=${days}`),
  weekly: (date?: string) =>
    api.get<WeeklyOut>(`${BASE}/weekly${date ? `?date=${encodeURIComponent(date)}` : ""}`),
  raw: (date: string) => api.get<RawOut>(`${BASE}/raw?date=${encodeURIComponent(date)}`),
  // ★ 全量同步历史日报（astrbot 下场 · 主人「同步理应同步历史所有日报」）
  ingestAll: () =>
    api.post<{ total: number; ok: number; skipped: number; failed: number; errors: string[] }>(
      `${BASE}/ingest-all`,
    ),
  ingest: (date?: string) =>
    api.post<IngestOut>(`${BASE}/ingest${date ? `?date=${encodeURIComponent(date)}` : ""}`),
  notes: (date: string) =>
    api.get<{ date: string | null; items: ReviewNote[] }>(
      `${BASE}/notes?date=${encodeURIComponent(date)}`,
    ),
  addNote: (date: string, content_md: string) =>
    api.post<ReviewNote>(`${BASE}/notes`, { date, content_md }),
  // ★ 2026-09-25（astrbot 下场 · 主人⑤「不能在复盘窗口内增减笔记」的"减"半边）
  deleteNote: (id: string) => api.delete<void>(`${BASE}/notes/${encodeURIComponent(id)}`),
};
