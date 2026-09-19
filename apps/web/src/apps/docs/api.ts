/**
 * 文档树模块数据请求层（集中在此，不散落各处）。
 * 跨插件拿数据一律走 HTTP（这里只用 docs 自己的 /api/v1/docs）。
 * 鉴权 / trace_id / RFC7807 解析由 @/shared/api/client 统一处理。
 */
import { api } from "@/shared/api/client";

export interface DocsNode {
  id: string;
  parent_id: string | null;
  kind: "folder" | "doc";
  name: string;
  sort: number;
  meta_json: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  children?: DocsNode[];
}

export interface DocsNodeDetail extends DocsNode {
  format: string | null;
  body: string | null;
}

export interface DocsPage<T = DocsNode> {
  items: T[];
  next_cursor: string | null;
}

export interface DocsRevision {
  id: string;
  node_id: string;
  format: string;
  content: string;
  created_at: string;
}

const BASE = "/api/v1/docs";

export const docsApi = {
  /** 树查询：root 缺省 = 整片森林；返回子树（一次装配）。 */
  tree: (root?: string | null) => {
    const qs = root ? `?root=${encodeURIComponent(root)}` : "";
    return api.get<DocsNode[]>(`${BASE}/nodes${qs}`);
  },

  create: (body: {
    parent_id?: string | null;
    kind: "folder" | "doc";
    name: string;
    meta_json?: Record<string, unknown> | null;
  }) => api.post<DocsNode>(`${BASE}/nodes`, body),

  get: (id: string) => api.get<DocsNodeDetail>(`${BASE}/nodes/${id}`),

  update: (
    id: string,
    body: {
      name?: string;
      parent_id?: string | null;
      meta_json?: Record<string, unknown> | null;
      sort?: number;
    },
  ) => api.patch<DocsNode>(`${BASE}/nodes/${id}`, body),

  remove: (id: string) => api.delete<void>(`${BASE}/nodes/${id}`),

  trash: (cursor?: string | null) => {
    const qs = cursor ? `?cursor=${encodeURIComponent(cursor)}` : "";
    return api.get<DocsPage>(`${BASE}/trash${qs}`);
  },

  restore: (id: string) => api.post<DocsNode>(`${BASE}/trash/${id}/restore`),

  purge: (id: string) => api.delete<void>(`${BASE}/trash/${id}`),

  saveContent: (id: string, body: { format: string; body: string }) =>
    api.put<DocsNodeDetail>(`${BASE}/nodes/${id}/content`, body),

  revisions: (id: string) => api.get<DocsPage<DocsRevision>>(`${BASE}/nodes/${id}/revisions`),

  restoreRevision: (id: string, revId: string) =>
    api.post<DocsNodeDetail>(`${BASE}/nodes/${id}/revisions/${revId}/restore`),

  search: (q: string) => {
    const qs = q ? `?q=${encodeURIComponent(q)}` : "";
    return api.get<DocsPage>(`${BASE}/search${qs}`);
  },
};
