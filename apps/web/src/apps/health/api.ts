/** 健康插件数据请求层。鉴权 / RFC7807 由 @/shared/api/client 统一处理。 */
import { api } from "@/shared/api/client";

export type HealthKind = "symptom" | "medication" | "appointment" | "lab";

export interface HealthRecord {
  id: string;
  kind: HealthKind;
  title: string;
  occurred_at: string;
  severity: number | null;
  note: string | null;
  followup_needed: boolean;
  followup_due: string | null;
}

export interface HealthRecordInput {
  kind: HealthKind;
  title: string;
  occurred_at: string;
  severity?: number | null;
  note?: string | null;
  followup_needed?: boolean;
  followup_due?: string | null;
}

const BASE = "/api/v1/health";

export const healthApi = {
  /** from/to 后端已支持（router alias from），前端补暴露（D1 趋势聚合用）。 */
  list(params?: {
    kind?: string;
    from?: string;
    to?: string;
    followup_only?: boolean;
  }): Promise<HealthRecord[]> {
    const q = new URLSearchParams();
    if (params?.kind) q.set("kind", params.kind);
    if (params?.from) q.set("from", params.from);
    if (params?.to) q.set("to", params.to);
    if (params?.followup_only) q.set("followup_only", "true");
    const qs = q.toString();
    return api.get<HealthRecord[]>(`${BASE}/records${qs ? `?${qs}` : ""}`);
  },
  create(body: HealthRecordInput): Promise<HealthRecord> {
    return api.post<HealthRecord>(`${BASE}/records`, body);
  },
  update(id: string, body: Partial<HealthRecordInput>): Promise<HealthRecord> {
    return api.patch<HealthRecord>(`${BASE}/records/${id}`, body);
  },
  remove(id: string): Promise<void> {
    return api.delete<void>(`${BASE}/records/${id}`);
  },
  requestFollowup(id: string): Promise<{ ok: boolean; idempotency_key: string }> {
    return api.post<{ ok: boolean; idempotency_key: string }>(
      `${BASE}/records/${id}/request-followup`,
    );
  },
};
