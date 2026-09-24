/**
 * U2 · 聚合小日历视图侧测试（判据 J1-J8）。
 * 网络层全 mock：并发 GET 各插件 today-summary，三态可区分、逐分区独立降级。
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { ApiError } from "@/shared/api/client";
import { TimeWidget } from "./TimeWidget";

vi.mock("@/shared/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/shared/api/client")>("@/shared/api/client");
  return { ...actual, api: { get: vi.fn() } };
});

import { api } from "@/shared/api/client";
import { useDesktopStore } from "../store";

function wrapper(): { el: ReactNode } {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return {
    el: (
      <QueryClientProvider client={qc}>
        <TimeWidget />
      </QueryClientProvider>
    ),
  };
}

const okResp = (items: unknown[]) => ({ title: "今日", items });

describe("U2 · TimeWidget（聚合小日历视图侧）", () => {
  beforeEach(() => {
    vi.mocked(api.get).mockReset();
  });
  afterEach(() => {
    cleanup();
  });

  it("J1 · 点击时钟展开面板，Esc 关闭", async () => {
    vi.mocked(api.get).mockResolvedValue(okResp([]));
    const { el } = wrapper();
    const { container } = render(el);
    expect(container.querySelector("[data-testid='today-summary-panel']")).toBeNull();
    fireEvent.click(screen.getByLabelText(/当前时间/));
    expect(container.querySelector("[data-testid='today-summary-panel']")).toBeTruthy();
    // 四分区常驻
    await waitFor(() => expect(screen.getByTestId("today-sum-calendar")).toBeTruthy());
    expect(screen.getByTestId("today-sum-todo")).toBeTruthy();
    expect(screen.getByTestId("today-sum-diary")).toBeTruthy();
    expect(screen.getByTestId("today-sum-review")).toBeTruthy();
    // Esc 关闭
    fireEvent.keyDown(document, { key: "Escape" });
    expect(container.querySelector("[data-testid='today-summary-panel']")).toBeNull();
  });

  it("J3 · 未安装（404）→ 显示「未安装 · 去安装」占位（不消失）", async () => {
    vi.mocked(api.get).mockRejectedValue(
      new ApiError({ type: "about:blank", title: "404", status: 404, detail: "no" }),
    );
    const { el } = wrapper();
    render(el);
    fireEvent.click(screen.getByLabelText(/当前时间/));
    // 四分区全部 404 → 四块「未安装」占位都渲染
    await waitFor(() => expect(screen.getAllByText(/未安装 · 去安装/).length).toBe(4));
  });

  it("J4 · 已安装但空数据 → 空态「今日暂无X」", async () => {
    vi.mocked(api.get).mockResolvedValue(okResp([]));
    const { el } = wrapper();
    render(el);
    fireEvent.click(screen.getByLabelText(/当前时间/));
    await waitFor(() => expect(screen.getByText("今日暂无待办")).toBeTruthy());
    expect(screen.getByText("今日暂无日记")).toBeTruthy();
  });

  it("J5 · 有数据 → 渲染列表（text + 数量）", async () => {
    vi.mocked(api.get).mockImplementation(async (url: string) => {
      if (url.startsWith("/api/v1/calendar")) {
        return { title: "今日日程", items: [{ text: "开周会 10:00", state: "info" }] };
      }
      if (url.startsWith("/api/v1/todo")) {
        return {
          title: "待办",
          items: [
            { text: "交房租", state: "due" },
            { text: "写周报", state: "done" },
          ],
        };
      }
      return okResp([]);
    });
    const { el } = wrapper();
    render(el);
    fireEvent.click(screen.getByLabelText(/当前时间/));
    await waitFor(() => expect(screen.getByText("开周会 10:00")).toBeTruthy());
    expect(screen.getByText("交房租")).toBeTruthy();
    expect(screen.getByText("写周报")).toBeTruthy();
    // 请求的是各插件自供端点（规范 v1）
    expect(vi.mocked(api.get).mock.calls.map((c) => c[0])).toContain(
      "/api/v1/calendar/today-summary",
    );
  });

  it("J6 · 单插件 5xx → 该分区「暂时不可用」，其余分区照常（独立降级）", async () => {
    vi.mocked(api.get).mockImplementation(async (url: string) => {
      if (url.startsWith("/api/v1/diary")) {
        throw new ApiError({ type: "about:blank", title: "500", status: 500, detail: "boom" });
      }
      return okResp([{ text: "正常条目" }]);
    });
    const { el } = wrapper();
    render(el);
    fireEvent.click(screen.getByLabelText(/当前时间/));
    // 其余分区先渲染（证明 diary 没拖垮整面板）
    await waitFor(() => expect(screen.getAllByText("正常条目").length).toBe(3));
    // diary 分区独立降级为「暂时不可用」（不是「没数据」，更不是消失）
    await waitFor(() => expect(screen.getByTestId("today-sum-diary-err")).toBeTruthy());
    expect(screen.getAllByText("暂时不可用").length).toBe(1);
  });

  it("J6b · 分区头点击 → 打开对应插件窗口", async () => {
    vi.mocked(api.get).mockResolvedValue(okResp([]));
    const openWindow = vi
      .spyOn(useDesktopStore.getState(), "openWindow")
      .mockImplementation(() => {});
    const { el } = wrapper();
    render(el);
    fireEvent.click(screen.getByLabelText(/当前时间/));
    await waitFor(() => expect(screen.getByText("待办")).toBeTruthy());
    fireEvent.click(screen.getByText("待办"));
    expect(openWindow).toHaveBeenCalledWith("todo");
    openWindow.mockRestore();
  });
});
