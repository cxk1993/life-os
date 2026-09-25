/** query 前端冒烟。网络全 mock。 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import QueryApp from "./QueryApp";

vi.mock("./api", () => ({
  queryApi: {
    presets: vi.fn().mockResolvedValue({
      items: [
        { id: "q_open_overdue", title: "open overdue" },
        { id: "q_free_slots_today", title: "free slots today" },
      ],
    }),
    run: vi.fn().mockResolvedValue({
      query: { id: "q_open_overdue", empty_text: "今天没有逾期" },
      rows: [{ title: "交报告", due: "2026-09-20" }],
      row_count: 1,
      empty: false,
    }),
  },
}));

function wrap() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

beforeEach(() => vi.clearAllMocks());

describe("QueryApp", () => {
  it("列出预置并点击执行", async () => {
    const { queryApi } = await import("./api");
    render(<QueryApp />, { wrapper: wrap() });
    await waitFor(() => {
      expect(screen.getByText("open overdue")).toBeTruthy();
    });
    fireEvent.click(screen.getByText("open overdue"));
    await waitFor(() => {
      expect(queryApi.run).toHaveBeenCalledWith("q_open_overdue", undefined);
    });
    await waitFor(() => {
      expect(screen.getByText(/交报告/)).toBeTruthy();
    });
  });

  it("空结果显示 empty_text", async () => {
    const { queryApi } = await import("./api");
    vi.mocked(queryApi.run).mockResolvedValueOnce({
      query: { id: "q_x", empty_text: "今天没有逾期，真棒" },
      rows: [],
      row_count: 0,
      empty: true,
    });
    render(<QueryApp />, { wrapper: wrap() });
    await waitFor(() => expect(screen.getByText("open overdue")).toBeTruthy());
    fireEvent.click(screen.getByText("open overdue"));
    await waitFor(() => {
      expect(screen.getByText(/今天没有逾期，真棒/)).toBeTruthy();
    });
  });
});
