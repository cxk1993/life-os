/**
 * 笔记模块数据请求层。
 * 列表只有索引；全文只在 get 单篇时经桥拉取。
 */
import { api } from "@/shared/api/client";

export interface NoteLib {
  id: string;
  key: string;
  name: string;
  enabled: boolean;
  md_count: number;
}

export interface NoteBrief {
  id: string;
  lib_id: string;
  lib_key: string;
  rel_path: string;
  title: string;
  excerpt: string;
  mtime: number;
  size: number;
  synced_at: string | null;
}

export interface NoteDetail extends NoteBrief {
  content: string;
}

export interface SearchOut {
  items: NoteBrief[];
  total: number;
}

export interface SyncResult {
  lib_key: string;
  upserted: number;
  removed: number;
  md_count: number;
}

const BASE = "/api/v1/notes";

export const notesApi = {
  libs: () => api.get<NoteLib[]>(`${BASE}/libs`),
  createLib: (body: { key: string; name?: string }) =>
    api.post<NoteLib>(`${BASE}/libs`, body),
  syncLib: (libId: string) => api.post<SyncResult>(`${BASE}/libs/${libId}/sync`),
  search: (q?: string, libId?: string) => {
    const p = new URLSearchParams();
    if (q) p.set("q", q);
    if (libId) p.set("lib_id", libId);
    const qs = p.toString();
    return api.get<SearchOut>(`${BASE}/search${qs ? `?${qs}` : ""}`);
  },
  get: (id: string) => api.get<NoteDetail>(`${BASE}/notes/${id}`),
};
