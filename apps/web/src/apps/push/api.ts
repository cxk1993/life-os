/**
 * push 插件数据请求层（Web Push 浏览器推送）。
 * 鉴权 / RFC7807 由 @/shared/api/client 统一处理。
 *
 * ★ 与后端 `modules/push/router.py` 的端点一一对应（契约以 router 为准）：
 *   /health  /vapid-public-key  /subscribe(POST|DELETE)  /subscriptions  /send  /logs
 */
import { api } from "@/shared/api/client";

export interface PushHealth {
  ok: boolean;
  enabled: boolean;
  vapid_ready: boolean;
  pywebpush_installed: boolean;
  subscriptions_active: number;
}

export interface PushSubscriptionRow {
  id: string;
  endpoint_prefix: string;
  user_agent: string | null;
  active: boolean;
  last_sent_at: string | null;
  last_status: number | null;
  fail_count: number;
  created_at: string;
}

export interface PushLogRow {
  id: string;
  topic: string;
  title: string;
  body: string | null;
  ok: boolean;
  detail: string | null;
  sent_at: string | null;
}

export interface SubscribePayload {
  endpoint: string;
  keys: { p256dh: string; auth: string };
  user_agent?: string | null;
}

export interface SendPayload {
  title: string;
  body?: string;
  url?: string;
  tag?: string;
}

export interface SendResult {
  ok: boolean;
  sent: number;
  pruned: number;
  detail: string | null;
}

const BASE = "/api/v1/push";

export const pushApi = {
  health(): Promise<PushHealth> {
    return api.get<PushHealth>(`${BASE}/health`);
  },
  /** VAPID 公钥（前端 pushManager.subscribe 用；未配置时后端 400）。 */
  vapidPublicKey(): Promise<{ public_key: string }> {
    return api.get<{ public_key: string }>(`${BASE}/vapid-public-key`);
  },
  subscribe(body: SubscribePayload): Promise<PushSubscriptionRow> {
    return api.post<PushSubscriptionRow>(`${BASE}/subscribe`, body);
  },
  unsubscribe(endpoint: string): Promise<{ ok: boolean }> {
    return api.delete<{ ok: boolean }>(
      `${BASE}/subscribe?endpoint=${encodeURIComponent(endpoint)}`,
    );
  },
  subscriptions(): Promise<PushSubscriptionRow[]> {
    return api.get<PushSubscriptionRow[]>(`${BASE}/subscriptions`);
  },
  send(body: SendPayload): Promise<SendResult> {
    return api.post<SendResult>(`${BASE}/send`, body);
  },
  logs(limit = 50): Promise<PushLogRow[]> {
    return api.get<PushLogRow[]>(`${BASE}/logs?limit=${limit}`);
  },
};
