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

export interface TreeNode {
  id: string;
  title: string;
  rel_path: string;
  is_dir: boolean;
  children: TreeNode[];
}

export interface NoteTree {
  lib_id: string;
  lib_key: string;
  root: TreeNode;
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
  createLib: (body: { key: string; name?: string }) => api.post<NoteLib>(`${BASE}/libs`, body),
  syncLib: (libId: string) => api.post<SyncResult>(`${BASE}/libs/${libId}/sync`),
  search: (q?: string, libId?: string) => {
    const p = new URLSearchParams();
    if (q) p.set("q", q);
    if (libId) p.set("lib_id", libId);
    const qs = p.toString();
    return api.get<SearchOut>(`${BASE}/search${qs ? `?${qs}` : ""}`);
  },
  get: (id: string) => api.get<NoteDetail>(`${BASE}/notes/${id}`),
  // ★ 2026-09-25（astrbot 下场 · 主人⑤「像 obsidian 同步文件夹结构树」「笔记无法新建/保存」）：
  //   后端早已提供 tree / 新建 / 编辑 端点，前端此前未接 —— 本刀补齐。
  tree: (libId: string) => api.get<NoteTree>(`${BASE}/libs/${libId}/tree`),
  createNote: (body: { lib_id: string; title?: string; rel_path: string; content?: string }) =>
    api.post<NoteDetail>(`${BASE}/libs/${body.lib_id}/notes`, body),
  updateNote: (id: string, body: { title?: string; content?: string }) =>
    api.put<NoteDetail>(`${BASE}/notes/${id}`, body),
};
