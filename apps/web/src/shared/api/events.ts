/**
 * 内核事件总线（SSE 订阅）。
 *
 * 总纲 §1.4：所有模块事件统一经 `GET /api/v1/events/subscribe` 的 SSE 流推送。
 * 这里做：自动重连 + 指数退避；后端未就绪时静默降级，不抛不崩。
 *
 * 模块侧用 `usePluginEvent(type, cb)` 订阅自己关心的事件。
 */

import { useEffect } from "react";

import { api, ApiError } from "./client";

export interface PluginEventEnvelope {
  type: string;
  payload?: unknown;
}

type Handler = (payload: unknown) => void;

const SSE_URL = "/api/v1/events/subscribe";
const MAX_BACKOFF = 30_000;

class EventBus {
  private es: EventSource | null = null;
  private handlers = new Map<string, Set<Handler>>();
  private retry = 0;
  private timer: ReturnType<typeof setTimeout> | null = null;
  /** 取票期间的重入保护：多个订阅同时触发时只换一次票。 */
  private connecting = false;

  subscribe(type: string, handler: Handler): () => void {
    let set = this.handlers.get(type);
    if (!set) {
      set = new Set();
      this.handlers.set(type, set);
    }
    set.add(handler);
    void this.connect();
    return () => {
      const s = this.handlers.get(type);
      if (!s) return;
      s.delete(handler);
      if (s.size === 0) this.handlers.delete(type);
      if (this.handlers.size === 0) this.disconnect();
    };
  }

  private dispatch(type: string, payload: unknown): void {
    this.handlers.get(type)?.forEach((h) => {
      try {
        h(payload);
      } catch {
        /* 单个订阅者出错不影响其它 */
      }
    });
  }

  /**
   * 换取 SSE 入场券（F2 加固，2026-09-23）。
   *
   * 为什么需要：浏览器原生 `EventSource` **不能带自定义 header**，所以 SSE 的
   * 鉴权只能走 query；而把 access token 直接拼进 URL 会进浏览器历史 / 代理日志 /
   * Referer —— 故先用已鉴权的 HTTP 请求换一张「60 秒 + type=sse」的短时票据。
   *
   * 返回 null 的语义 = 「本次不连」（未登录 / 票据拿不到），调用方静默等待，
   * **不做无谓的退避轰炸** —— 登录后组件重新订阅会自然触发重连。
   */
  private async fetchTicket(): Promise<string | null> {
    try {
      const res = await api.post<{ ticket: string }>("/api/v1/events/ticket", {});
      return res?.ticket ?? null;
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) return null; // 未登录：静默等
      throw e; // 网络/后端异常：交给上层退避重连
    }
  }

  private async connect(): Promise<void> {
    if (this.es || this.connecting || typeof EventSource === "undefined") return;
    this.connecting = true;
    let es: EventSource;
    try {
      const ticket = await this.fetchTicket();
      if (!ticket) return; // 未登录：不发无谓重连
      es = new EventSource(`${SSE_URL}?ticket=${encodeURIComponent(ticket)}`);
    } catch {
      this.scheduleReconnect();
      return;
    } finally {
      this.connecting = false;
    }
    this.es = es;
    es.onmessage = (ev: MessageEvent) => {
      this.retry = 0;
      try {
        const env = JSON.parse(ev.data) as PluginEventEnvelope;
        if (env && typeof env.type === "string") this.dispatch(env.type, env.payload);
      } catch {
        /* 非法消息忽略 */
      }
    };
    es.onerror = () => {
      this.disconnect();
      this.scheduleReconnect(); // 票据 60s 过期后重连会自动换新票
    };
  }

  private scheduleReconnect(): void {
    if (this.timer) return;
    const delay = Math.min(MAX_BACKOFF, 500 * 2 ** this.retry);
    this.retry += 1;
    this.timer = setTimeout(() => {
      this.timer = null;
      void this.connect();
    }, delay);
  }

  private disconnect(): void {
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }
    if (this.es) {
      this.es.close();
      this.es = null;
    }
  }
}

export const eventBus = new EventBus();

/** 订阅某类插件事件；组件卸载自动退订。 */
export function usePluginEvent(type: string, handler: Handler): void {
  useEffect(() => eventBus.subscribe(type, handler), [type, handler]);
}
