import { api } from "@/shared/api/client";

// ★ 与 T19 的 CapabilityEntry 同形状（字段名对齐，不 import 对方）
export interface CatalogEntry {
  id: string;
  name: string;
  kind: string;
  url: string | null;
  endpoint: string | null;
  auth_ref: string | null;
  capabilities: string[];
  enabled: boolean;
  note: string | null;
  source: string; // plugin | web_entry | kernel | manual
}

export interface CatalogOut {
  entries: CatalogEntry[];
  generatedAt: string;
  counts: Record<string, number>;
}

export interface ManualEntryCreate {
  name: string;
  kind?: string;
  url?: string | null;
  endpoint?: string | null;
  auth_ref?: string | null;
  capabilities?: string[];
  note?: string | null;
  catalog_id?: string | null;
  enabled?: boolean;
}

export interface ManualEntryUpdate {
  name?: string | null;
  kind?: string | null;
  url?: string | null;
  endpoint?: string | null;
  auth_ref?: string | null;
  capabilities?: string[] | null;
  note?: string | null;
  enabled?: boolean | null;
}

const BASE = "/api/v1/catalog";

export const catalogApi = {
  getCatalog: () => api.get<CatalogOut>(`${BASE}`),
  createManual: (body: ManualEntryCreate) => api.post<CatalogEntry>(`${BASE}/manual`, body),
  updateManual: (id: string, body: ManualEntryUpdate) =>
    api.patch<CatalogEntry>(`${BASE}/manual/${encodeURIComponent(id)}`, body),
  deleteManual: (id: string) => api.delete<void>(`${BASE}/manual/${encodeURIComponent(id)}`),
};
