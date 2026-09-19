/**
 * 日记模块数据请求层（薄壳：定位/视图端点；正文读写直接复用 docsApi）。
 * 鉴权 / trace_id / RFC7807 解析由 @/shared/api/client 统一处理。
 */
import { api } from "@/shared/api/client";

export interface DiaryEntry {
  node_id: string;
  path: string;
  exists: boolean;
  date: string;
}

export interface DiaryToday {
  date: string;
  node_id: string;
  path: string;
  exists: boolean;
}

export interface DiaryMonth {
  year: number;
  month: number;
  days: string[];
}

export interface InboxItem {
  id: string;
  name: string;
  created_at: string | null;
}

const BASE = "/api/v1/diary";

export const diaryApi = {
  today: () => api.get<DiaryToday>(`${BASE}/today`),
  entry: (date?: string) => {
    const qs = date ? `?date=${encodeURIComponent(date)}` : "";
    return api.get<DiaryEntry>(`${BASE}/entry${qs}`);
  },
  month: (year: number, month: number) =>
    api.get<DiaryMonth>(`${BASE}/month?year=${year}&month=${month}`),
  inbox: () => api.get<{ items: InboxItem[] }>(`${BASE}/inbox`),
  capture: () => api.post<{ node_id: string; path: string; name: string }>(`${BASE}/capture`),
  consolidate: (node_id: string, date: string) =>
    api.post<{ node_id: string; target_date: string }>(`${BASE}/consolidate`, { node_id, date }),
};
