/** mcp-console 的 API 封装（走内核统一 client，JWT 由 client 注入）。 */
import { api } from "@/shared/api/client";

export interface ToolInfo {
  name: string;
  description: string;
  method: string;
  path: string;
  scope: string;
  plugin_id: string;
}

export interface PatRecord {
  id: string;
  name: string;
  token_prefix: string;
  scopes: string[];
  created_at: string;
  expires_at: string | null;
  last_used_at: string | null;
  revoked_at: string | null;
}

export interface PatCreated extends PatRecord {
  /** ★ 明文只在本响应出现一次 */
  token: string;
}

export interface AuditRecord {
  id: string;
  actor: string;
  action: string;
  target: string;
  at: string;
}

export const mcpApi = {
  tools: () => api.get<ToolInfo[]>("/api/v1/mcp/tools"),
  auditLogs: (limit = 100) => api.get<AuditRecord[]>(`/api/v1/mcp/audit-logs?limit=${limit}`),
  listPats: () => api.get<PatRecord[]>("/api/v1/mcp/pats"),
  createPat: (name: string, scopes: string[]) =>
    api.post<PatCreated>("/api/v1/mcp/pats", { name, scopes }),
  patchPat: (id: string, scopes: string[]) =>
    api.patch<PatRecord>(`/api/v1/mcp/pats/${id}`, { scopes }),
  revokePat: (id: string) => api.delete<void>(`/api/v1/mcp/pats/${id}`),
};
