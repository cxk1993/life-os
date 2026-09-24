/**
 * U3 · todo dock 卡测试（dock 数据规范 v1：三态可区分）。
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { ApiError } from "@/shared/api/client";
import { DockCard } from "../index";
import { useDesktopStore } from "../../../kernel/store";

vi.mock("@/shared/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/shared/api/client")>("@/shared/api/client");
  return { ...actual, api: { get: vi.fn() } };
});

import { api } from "@/shared/api/client";

function wrapper(): { el: ReactNode } {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, retryDelay: 0 } },
  });
  return {
    el: (
      <QueryClientProvider client={qc}>
        <DockCard />
      </QueryClientProvider>
    ),
  };
}

describe("U3 · todo DockCard（desktop.dock-right 首例）", () => {
  beforeEach(() => {
    vi.mocked(api.get).mockReset();
  });
  afterEach(() => {
    cleanup();
  });

  it("D1 · 有数据 → 列表渲染（逾期 alert / 今日 due / 已完成计数）", async () => {
    vi.mocked(api.get).mockResolvedValue({
      title: "今日待办 3 项",
      items: [
        { text: "昨天逾期", state: "alert", count: 1 },
        { text: "今天开会", state: "due", count: 1 },
        { text: "写周报", state: "due" },
      ],
      done: 2,
      link: "/todo",
    });
    const { el } = wrapper();
    render(el);
    await waitFor(() => expect(screen.getByText("昨天逾期")).toBeTruthy());
    expect(screen.getByText("今天开会")).toBeTruthy();
    expect(screen.getByText("已完成 2 项")).toBeTruthy();
    // 请求 today-summary 端点
    expect(vi.mocked(api.get).mock.calls.map((c) => c[0])).toContain("/api/v1/todo/today-summary");
  });

  it("D2 · 空数据 → 「今日暂无待办」（200 空，非未安装）", async () => {
    vi.mocked(api.get).mockResolvedValue({ title: "今日待办 0 项", items: [], done: 0 });
    const { el } = wrapper();
    render(el);
    await waitFor(() => expect(screen.getByText("今日暂无待办")).toBeTruthy());
  });

  it("D3 · 404 → 「未安装 · 去安装」占位（不消失）", async () => {
    vi.mocked(api.get).mockRejectedValue(
      new ApiError({ type: "about:blank", title: "404", status: 404, detail: "no" }),
    );
    const { el } = wrapper();
    render(el);
    await waitFor(() => expect(screen.getByTestId("todo-dock-na")).toBeTruthy());
    expect(screen.getByText(/未安装 · 去安装/)).toBeTruthy();
  });

  it("D4 · 5xx → 「暂时不可用」（独立降级）", async () => {
    vi.mocked(api.get).mockRejectedValue(
      new ApiError({ type: "about:blank", title: "500", status: 500, detail: "boom" }),
    );
    const { el } = wrapper();
    render(el);
    await waitFor(() => expect(screen.getByTestId("todo-dock-err")).toBeTruthy());
    expect(screen.getByText("暂时不可用")).toBeTruthy();
  });

  it("D5 · 分区头点击 → 打开 todo 窗口", async () => {
    vi.mocked(api.get).mockResolvedValue({ items: [{ text: "x", state: "info" }] });
    const openWindow = vi
      .spyOn(useDesktopStore.getState(), "openWindow")
      .mockImplementation(() => {});
    const { el } = wrapper();
    render(el);
    await waitFor(() => expect(screen.getByText("待办")).toBeTruthy());
    fireEvent.click(screen.getByText("待办"));
    expect(openWindow).toHaveBeenCalledWith("todo");
    openWindow.mockRestore();
  });
});
