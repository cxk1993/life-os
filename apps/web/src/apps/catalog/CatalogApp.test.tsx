import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import CatalogApp from "./CatalogApp";
import { catalogApi } from "./api";

// mock api 层
vi.mock("./api", () => ({
  catalogApi: {
    getCatalog: vi.fn(),
    createManual: vi.fn(),
    updateManual: vi.fn(),
    deleteManual: vi.fn(),
  },
}));

const apiMock = catalogApi as unknown as {
  getCatalog: ReturnType<typeof vi.fn>;
  createManual: ReturnType<typeof vi.fn>;
  updateManual: ReturnType<typeof vi.fn>;
  deleteManual: ReturnType<typeof vi.fn>;
};

const sampleCatalog = {
  entries: [
    {
      id: "plugin.calendar",
      name: "日程表",
      kind: "web+rest",
      url: null,
      endpoint: "/api/v1/calendar",
      auth_ref: "none",
      capabilities: ["calendar.event.read", "calendar.event.write"],
      enabled: true,
      note: "可嵌套日程",
      source: "plugin",
    },
    {
      id: "manual-abc",
      name: "我的 API",
      kind: "web+rest",
      url: null,
      endpoint: "https://api.example.com/v1",
      auth_ref: "pat:env:EXAMPLE_TOKEN",
      capabilities: ["myapi.read"],
      enabled: true,
      note: "手动导入",
      source: "manual",
    },
  ],
  generatedAt: "2026-09-20T00:00:00Z",
  counts: { plugin: 1, manual: 1 },
};

function renderApp() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <CatalogApp />
    </QueryClientProvider>,
  );
}

describe("CatalogApp", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMock.getCatalog.mockResolvedValue(sampleCatalog);
  });

  it("加载后按来源分组展示条目", async () => {
    renderApp();
    await waitFor(() => expect(screen.getByText("日程表")).toBeTruthy());
    expect(screen.getByText("插件能力")).toBeTruthy();
    // 「手动导入」同时是分组标题和按钮文案，用 getAllByText 断言至少出现
    expect(screen.getAllByText("手动导入").length).toBeGreaterThan(0);
    expect(screen.getByText("我的 API")).toBeTruthy();
  });

  it("搜索过滤条目", async () => {
    renderApp();
    await waitFor(() => expect(screen.getByText("日程表")).toBeTruthy());
    const input = screen.getByPlaceholderText(/搜索能力/);
    fireEvent.change(input, { target: { value: "myapi" } });
    await waitFor(() => {
      expect(screen.queryByText("日程表")).toBeFalsy();
      expect(screen.getByText("我的 API")).toBeTruthy();
    });
  });

  it("手动条目可切换开关", async () => {
    apiMock.updateManual.mockResolvedValue({
      ...sampleCatalog.entries[1],
      enabled: false,
    });
    renderApp();
    await waitFor(() => expect(screen.getByText("我的 API")).toBeTruthy());
    const toggle = screen.getAllByTitle("点击停用")[0];
    fireEvent.click(toggle);
    await waitFor(() =>
      expect(apiMock.updateManual).toHaveBeenCalledWith("manual-abc", { enabled: false }),
    );
  });

  it("手动条目可删除", async () => {
    apiMock.deleteManual.mockResolvedValue(undefined);
    renderApp();
    await waitFor(() => expect(screen.getByText("我的 API")).toBeTruthy());
    const del = screen.getAllByTitle("删除")[0];
    fireEvent.click(del);
    await waitFor(() => expect(apiMock.deleteManual).toHaveBeenCalledWith("manual-abc"));
  });

  it("手动导入表单：新建条目", async () => {
    apiMock.createManual.mockResolvedValue({
      ...sampleCatalog.entries[1],
      id: "manual-new",
      name: "新建的 API",
    });
    renderApp();
    await waitFor(() => expect(screen.getByText("日程表")).toBeTruthy());
    fireEvent.click(screen.getByText("+ 手动导入"));
    const nameInput = screen.getByPlaceholderText("名称 *");
    fireEvent.change(nameInput, { target: { value: "新建的 API" } });
    fireEvent.click(screen.getByRole("button", { name: "保存" }));
    await waitFor(() => expect(apiMock.createManual).toHaveBeenCalled());
  });
});
