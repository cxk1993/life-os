/** sidebar 前端冒烟。网络全 mock。 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import SidebarApp from "./SidebarApp";

vi.mock("@/shared/api/client", () => {
  const items = [
    {
      id: "s1",
      type: "link",
      label: "GitHub",
      abbr: "GH",
      href: "https://github.com",
      node_ref: "",
      group: "开发",
      order: 0,
      enabled: true,
    },
    {
      id: "s2",
      type: "note",
      label: "便签A",
      abbr: "",
      href: "",
      node_ref: "notes/便签/a",
      group: "",
      order: 1,
      enabled: false,
    },
  ];
  return {
    ApiError: class ApiError extends Error {
      detail?: string;
      constructor(msg: string) {
        super(msg);
        this.detail = msg;
      }
    },
    api: {
      get: vi.fn().mockResolvedValue({ items, count: 2 }),
      post: vi.fn().mockResolvedValue({ id: "new" }),
      patch: vi.fn().mockResolvedValue({}),
      delete: vi.fn().mockResolvedValue(undefined),
    },
  };
});

function wrap() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
});

describe("SidebarApp 自定义", () => {
  it("列出条目与分组筛选", async () => {
    render(<SidebarApp />, { wrapper: wrap() });
    await waitFor(() => expect(screen.getByText("GitHub")).toBeTruthy());
    expect(screen.getByText(/2 条/)).toBeTruthy();
  });

  it("类型切换：便签不显示链接框", async () => {
    render(<SidebarApp />, { wrapper: wrap() });
    fireEvent.change(screen.getByLabelText("类型"), { target: { value: "note" } });
    expect(screen.queryByLabelText("链接")).toBeNull();
    expect(screen.getByLabelText("笔记引用")).toBeTruthy();
  });

  it("禁用/启用按钮可点", async () => {
    const { api } = await import("@/shared/api/client");
    render(<SidebarApp />, { wrapper: wrap() });
    await waitFor(() => expect(screen.getByText("GitHub")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "禁用 GitHub" }));
    await waitFor(() => {
      expect(api.patch).toHaveBeenCalled();
    });
  });

  it("隐藏已禁用过滤", async () => {
    render(<SidebarApp />, { wrapper: wrap() });
    await waitFor(() => expect(screen.getByText("便签A")).toBeTruthy());
    fireEvent.click(screen.getByLabelText("隐藏已禁用"));
    await waitFor(() => {
      expect(screen.queryByText("便签A")).toBeNull();
    });
    expect(screen.getByText("GitHub")).toBeTruthy();
  });
});
