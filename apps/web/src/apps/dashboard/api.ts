/** dashboard 数据请求层。鉴权 / RFC7807 由 @/shared/api/client 统一处理。 */
import { api } from "@/shared/api/client";

export type ModuleStatus = "ok" | "timeout" | "error";

export interface UpstreamResult {
  status: ModuleStatus | "ok";
  detail?: string;
  path?: string;
  _path?: string;
  [key: string]: unknown;
}

export interface TodayCounts {
  calendar_events: number | null;
  todo_open: number | null;
  habits_done: number | null;
  habits_total: number | null;
}

export interface TodayBlock {
  date: string;
  calendar: UpstreamResult;
  todo: UpstreamResult;
  habits: UpstreamResult;
  counts: TodayCounts;
}

export interface MoneyBlock {
  snapshot: UpstreamResult;
  summary: UpstreamResult;
}

export interface ReviewBlock {
  source: UpstreamResult;
}

export interface GrowthBlock {
  axes: unknown[];
  placeholder: string;
}

export interface SystemEntry {
  id: string;
  name: string;
  status: ModuleStatus;
  detail?: string;
  path?: string;
  elapsed_ms?: number | null;
}

export interface CardHint {
  pluginId: string;
  name: string;
  slot: string;
  enabled?: boolean;
}

export interface Overview {
  date: string;
  today: TodayBlock;
  money: MoneyBlock;
  review: ReviewBlock;
  growth: GrowthBlock;
  system: SystemEntry[];
  cards: CardHint[];
  cards_hint: string;
  meta: Record<string, unknown>;
}

export interface TodayResponse extends TodayBlock {
  meta?: Record<string, unknown>;
}

export interface HealthOfSystem {
  date: string;
  system: SystemEntry[];
  meta: Record<string, unknown>;
}

const BASE = "/api/v1/dashboard";

/** 整数分 → 元字符串（本插件本地实现，不 import 其它插件）。 */
export function formatCents(cents: number | null | undefined): string {
  if (cents === null || cents === undefined || Number.isNaN(cents)) return "—";
  const sign = cents < 0 ? "-" : "";
  const abs = Math.abs(cents);
  const yuan = Math.floor(abs / 100);
  const fen = abs % 100;
  return `${sign}${yuan}.${String(fen).padStart(2, "0")}`;
}

export function isDegraded(status: string | undefined): boolean {
  return status === "timeout" || status === "error";
}

export const dashboardApi = {
  overview: () => api.get<Overview>(`${BASE}/overview`),
  today: () => api.get<TodayResponse>(`${BASE}/today`),
  healthOfSystem: () => api.get<HealthOfSystem>(`${BASE}/health-of-system`),
  growth: () => api.get<GrowthBlock>(`${BASE}/growth`),
  manifest: () => api.get<Record<string, unknown>>(`${BASE}/manifest`),
};
