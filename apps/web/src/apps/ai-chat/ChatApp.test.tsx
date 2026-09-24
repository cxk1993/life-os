/**
 * E7 · ai-chat 对话窗 UI 测试（TX-AI-CHAT-01 前端块）。
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

import { ApiError } from "@/shared/api/client";
import { ChatApp } from "./index";

vi.mock("@/shared/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/shared/api/client")>("@/shared/api/client");
  return { ...actual, api: { post: vi.fn() } };
});

import { api } from "@/shared/api/client";

describe("E7 · ChatApp（AI 对话窗前端块）", () => {
  beforeEach(() => {
    vi.mocked(api.post).mockReset();
  });
  afterEach(() => {
    cleanup();
  });

  it("C1 · 初始有欢迎消息 + 输入/发送就绪", () => {
    render(<ChatApp />);
    expect(screen.getByText(/内置 AI 助手/)).toBeTruthy();
    expect(screen.getByTestId("chat-input")).toBeTruthy();
    // 空输入发送禁用
    expect((screen.getByTestId("chat-send") as HTMLButtonElement).disabled).toBe(true);
  });

  it("C2 · 发送 → 消息追加 + 请求契约 + 回显回复", async () => {
    vi.mocked(api.post).mockResolvedValue({
      session_id: "default",
      reply: "Echo: 明天有什么安排？",
      audit: ["tool:calendar.query"],
      system: "…",
    });
    render(<ChatApp />);
    fireEvent.change(screen.getByTestId("chat-input"), { target: { value: "明天有什么安排？" } });
    fireEvent.click(screen.getByTestId("chat-send"));
    // 用户消息先出现
    await waitFor(() => expect(screen.getByText("明天有什么安排？")).toBeTruthy());
    // 请求契约
    expect(vi.mocked(api.post).mock.calls[0][0]).toBe("/api/v1/ai-chat/messages");
    expect(vi.mocked(api.post).mock.calls[0][1]).toEqual({
      text: "明天有什么安排？",
      session_id: "default",
    });
    // 助手回复
    await waitFor(() => expect(screen.getByText(/Echo: 明天有什么安排/)).toBeTruthy());
    // 工具轨迹可展开
    fireEvent.click(screen.getByText(/查看工具轨迹/));
    expect(screen.getByTestId("chat-audit")).toBeTruthy();
    expect(screen.getByText("tool:calendar.query")).toBeTruthy();
  });

  it("C3 · 5xx → 错误气泡「暂时不可用」（网关未就绪可区分）", async () => {
    vi.mocked(api.post).mockRejectedValue(
      new ApiError({ type: "about:blank", title: "500", status: 500, detail: "gateway" }),
    );
    render(<ChatApp />);
    fireEvent.change(screen.getByTestId("chat-input"), { target: { value: "你好" } });
    fireEvent.click(screen.getByTestId("chat-send"));
    await waitFor(() => expect(screen.getByText(/暂时不可用/)).toBeTruthy());
  });

  it("C4 · 输入为空不发送；发送后输入清空", async () => {
    vi.mocked(api.post).mockResolvedValue({
      session_id: "default",
      reply: "ok",
      audit: [],
      system: "",
    });
    render(<ChatApp />);
    const input = screen.getByTestId("chat-input") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "   " } });
    // 纯空白 → 发送仍禁用
    expect((screen.getByTestId("chat-send") as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(input, { target: { value: "正经问题" } });
    expect((screen.getByTestId("chat-send") as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(screen.getByTestId("chat-send"));
    await waitFor(() => expect(input.value).toBe(""));
  });
});
