/** 推送插件前端测试。网络与浏览器 API 全 mock（没有真推送服务，不伪造"已推送"）。 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import PushApp, { urlBase64ToUint8Array } from "./PushApp";

vi.mock("./api", () => ({
  pushApi: {
    health: vi.fn().mockResolvedValue({
      ok: true,
      enabled: true,
      vapid_ready: true,
      pywebpush_installed: true,
      subscriptions_active: 2,
    }),
    subscriptions: vi.fn().mockResolvedValue([
      {
        id: "s1",
        endpoint_prefix: "https://push.example.test/sub",
        user_agent: "Vitest/1.0",
        active: true,
        last_sent_at: null,
        last_status: null,
        fail_count: 0,
        created_at: new Date().toISOString(),
      },
    ]),
    logs: vi.fn().mockResolvedValue([]),
    vapidPublicKey: vi.fn(),
    subscribe: vi.fn(),
    unsubscribe: vi.fn(),
    send: vi.fn().mockResolvedValue({ ok: true, sent: 1, pruned: 0, detail: null }),
  },
}));

import { pushApi } from "./api";

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <PushApp />
    </QueryClientProvider>
  );
}

describe("urlBase64ToUint8Array", () => {
  it("解 base64url 并保留字节", () => {
    // "AQAB" 是 VAPID 公钥常见前缀（DER 头），base64url 与 base64 同形
    const out = urlBase64ToUint8Array("AQAB");
    expect(Array.from(out)).toEqual([1, 0, 1]);
  });

  it("处理 URL 安全字符 - 与 _", () => {
    // "-_8" → "+/8" → [251, 255]
    const out = urlBase64ToUint8Array("-_8");
    expect(Array.from(out)).toEqual([251, 255]);
  });
});

describe("PushApp", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("渲染三段主体：配置态 / 订阅 / 广播", async () => {
    render(wrap());
    expect(screen.getByText("推送通道")).toBeTruthy();
    expect(screen.getByText("本机订阅")).toBeTruthy();
    expect(screen.getByText("手动广播")).toBeTruthy();
  });

  it("展示服务端活跃订阅数与订阅清单", async () => {
    render(wrap());
    // health 的活跃订阅数
    expect(await screen.findByText("2")).toBeTruthy();
    // 订阅行的 UA
    expect(await screen.findByText("Vitest/1.0")).toBeTruthy();
  });

  it("jsdom 无 serviceWorker 时给出明确降级提示，不静默", async () => {
    render(wrap());
    expect(await screen.findByText(/当前浏览器不支持 Web Push/)).toBeTruthy();
  });

  it("点「发送测试推送」调用后端 /send", async () => {
    render(wrap());
    fireEvent.click(screen.getByText("发送测试推送"));
    await waitFor(() => expect(pushApi.send).toHaveBeenCalledTimes(1));
    expect(await screen.findByText(/广播结果：成功 1 条/)).toBeTruthy();
  });

  it("无订阅时给空态引导", async () => {
    vi.mocked(pushApi.subscriptions).mockResolvedValueOnce([]);
    render(wrap());
    expect(await screen.findByText(/还没有任何订阅/)).toBeTruthy();
  });

  it("健康检查失败时报错文案可见", async () => {
    vi.mocked(pushApi.health).mockRejectedValueOnce(new Error("boom"));
    render(wrap());
    expect(await screen.findByText(/健康检查失败：boom/)).toBeTruthy();
  });
});
