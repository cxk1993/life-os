/** AI 编排数据请求层。鉴权 / RFC7807 由 @/shared/api/client 统一处理。 */
import { api } from "@/shared/api/client";

export interface Agent {
  id: string;
  name: string;
  description: string;
  capabilities: string[];
  load: number;
  enabled: boolean;
  callback_url: string | null;
  last_seen: string | null;
  created_at: string;
  updated_at: string;
}

export interface AgentCreate {
  name: string;
  description?: string;
  capabilities?: string[];
  callback_url?: string | null;
  enabled?: boolean;
}

export interface AgentTask {
  id: string;
  title: string;
  description: string;
  status: "draft" | "queued" | "running" | "done" | "failed" | "cancelled";
  assignee: string | null;
  priority: number;
  result: string | null;
  result_status: string | null;
  attempts: number;
  created_at: string;
  updated_at: string;
}

export interface Summary {
  tasks_total: number;
  draft: number;
  queued: number;
  running: number;
  done: number;
  failed: number;
  cancelled: number;
  agents_total: number;
  agents_enabled: number;
}

const BASE = "/api/v1/agents";

export const agentsApi = {
  list: () => api.get<Agent[]>(`${BASE}/agents`),
  create: (body: AgentCreate) => api.post<Agent>(`${BASE}/agents`, body),
  update: (id: string, body: Partial<Agent>) =>
    api.patch<Agent>(`${BASE}/agents/${id}`, body),
  remove: (id: string) => api.delete<void>(`${BASE}/agents/${id}`),
  listTasks: () => api.get<AgentTask[]>(`${BASE}/tasks`),
  summary: () => api.get<Summary>(`${BASE}/summary`),
};
