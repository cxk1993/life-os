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

// ★ mcp-console 轻 UI：T18 MCP 工具在目录页展示承接（只读 /api/v1/mcp/tools）
//   与 mcp/api.ts 的 ToolInfo 同形状（不 import 对方，避免跨领地耦合）
export interface CatalogMcpTool {
  name: string;
  description: string;
  method: string;
  path: string;
  scope: string;
  plugin_id: string;
}

// ★ E2 权限徽标：T20 插件清单的最小同形状类型（不 import 内核，避免跨领地耦合）。
//   只读 /api/v1/plugins，取每个插件「运行时实际授权」的 permissions
//   （后端 granted_permissions 优先、无授权记录则回退 manifest 声明）。
//   permissions 双格式：旧=string[]（如 ["db:own","net:out:localhost"]），
//   新（B 路径后）={filesystem,network,subprocess} 布尔对象。
export type PluginPermissions = string[] | Record<string, boolean>;

export interface PluginInfoLite {
  id: string;
  name?: string | null;
  enabled?: boolean;
  permissions?: PluginPermissions | null;
}

export interface PluginsOut {
  plugins: PluginInfoLite[];
  count?: number;
}

const BASE = "/api/v1/catalog";

export const catalogApi = {
  getCatalog: () => api.get<CatalogOut>(`${BASE}`),
  createManual: (body: ManualEntryCreate) => api.post<CatalogEntry>(`${BASE}/manual`, body),
  updateManual: (id: string, body: ManualEntryUpdate) =>
    api.patch<CatalogEntry>(`${BASE}/manual/${encodeURIComponent(id)}`, body),
  deleteManual: (id: string) => api.delete<void>(`${BASE}/manual/${encodeURIComponent(id)}`),
  mcpTools: () => api.get<CatalogMcpTool[]>("/api/v1/mcp/tools"),
  // ★ E2：只读复用现成插件清单端点（零后端改动），取 granted permissions
  plugins: () => api.get<PluginsOut>("/api/v1/plugins"),
};
