/**
 * 内核事件总线（SSE 订阅）。
 *
 * 总纲 §1.4：所有模块事件统一经 `GET /api/v1/events/subscribe` 的 SSE 流推送。
 * 这里做：自动重连 + 指数退避；后端未就绪时静默降级，不抛不崩。
 *
 * 模块侧用 `usePluginEvent(type, cb)` 订阅自己关心的事件。
 */

import { useEffect } from "react";

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

  subscribe(type: string, handler: Handler): () => void {
    let set = this.handlers.get(type);
    if (!set) {
      set = new Set();
      this.handlers.set(type, set);
    }
    set.add(handler);
    this.connect();
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

  private connect(): void {
    if (this.es || typeof EventSource === "undefined") return;
    let es: EventSource;
    try {
      es = new EventSource(SSE_URL);
    } catch {
      this.scheduleReconnect();
      return;
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
      this.scheduleReconnect();
    };
  }

  private scheduleReconnect(): void {
    if (this.timer) return;
    const delay = Math.min(MAX_BACKOFF, 500 * 2 ** this.retry);
    this.retry += 1;
    this.timer = setTimeout(() => {
      this.timer = null;
      this.connect();
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
