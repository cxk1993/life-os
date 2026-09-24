/** export 前端冒烟。网络全 mock。 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import ExportApp from "./ExportApp";

vi.mock("./api", () => ({
  exportApi: {
    profiles: vi.fn().mockResolvedValue({
      items: [
        { id: "full", title: "数据 + 文档树" },
        { id: "data-only", title: "仅业务数据" },
      ],
    }),
    preview: vi.fn().mockResolvedValue({
      schema_version: "1.0",
      profile: "full",
      secret_policy: "omit+redact",
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

describe("ExportApp", () => {
  it("选 profile 出预览 JSON", async () => {
    const { exportApi } = await import("./api");
    render(<ExportApp />, { wrapper: wrap() });
    await waitFor(() => {
      expect(screen.getByText("数据 + 文档树")).toBeTruthy();
    });
    fireEvent.click(screen.getByText("数据 + 文档树"));
    await waitFor(() => {
      expect(exportApi.preview).toHaveBeenCalledWith("full");
    });
    await waitFor(() => {
      const pre = document.querySelector(".export-json");
      expect(pre?.textContent).toMatch(/secret_policy/);
    });
  });
});
