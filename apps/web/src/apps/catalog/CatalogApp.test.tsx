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
    mcpTools: vi.fn(),
    plugins: vi.fn(),
  },
}));

const apiMock = catalogApi as unknown as {
  getCatalog: ReturnType<typeof vi.fn>;
  createManual: ReturnType<typeof vi.fn>;
  updateManual: ReturnType<typeof vi.fn>;
  deleteManual: ReturnType<typeof vi.fn>;
  mcpTools: ReturnType<typeof vi.fn>;
  plugins: ReturnType<typeof vi.fn>;
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

const sampleMcpTools = [
  {
    name: "calendar.event.write",
    description: "写入日程事件",
    method: "POST",
    path: "/api/v1/calendar/events",
    scope: "calendar:write",
    plugin_id: "calendar",
  },
  {
    name: "todo.item.create",
    description: "创建待办",
    method: "POST",
    path: "/api/v1/todo/items",
    scope: "todo:write",
    plugin_id: "todo",
  },
];

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
    apiMock.mcpTools.mockResolvedValue(sampleMcpTools);
    // E2：默认 calendar 插件持 db:own（无网络）；各用例可覆盖
    apiMock.plugins.mockResolvedValue({
      plugins: [{ id: "calendar", permissions: ["db:own"] }],
      count: 1,
    });
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

  it("展示 MCP 工具区块（按插件分组）", async () => {
    renderApp();
    await waitFor(() => expect(screen.getByText("AI 工具（MCP）")).toBeTruthy());
    // 表格里应出现两个工具名（MCP 区块内）
    const section = screen.getByText("AI 工具（MCP）").closest("section") as HTMLElement;
    expect(section).toBeTruthy();
    expect(section.querySelectorAll(".catalog-mcp-table tbody tr").length).toBe(2);
    expect(section.textContent).toContain("calendar.event.write");
    expect(section.textContent).toContain("todo.item.create");
    expect(section.textContent).toContain("写入日程事件");
  });

  it("MCP 工具列表为空时显示提示", async () => {
    apiMock.mcpTools.mockResolvedValue([]);
    renderApp();
    await waitFor(() => expect(screen.getByText("AI 工具（MCP）")).toBeTruthy());
    expect(screen.getByText(/当前没有插件声明 provides/)).toBeTruthy();
  });

  // ─────────── ★ E2 权限徽标（令21 五个用例） ───────────

  it("E2：旧数组 token 推出核心徽标，db:own 计入明细 1 且本机网络常显", async () => {
    apiMock.plugins.mockResolvedValue({
      plugins: [{ id: "calendar", permissions: ["db:own", "net:out:localhost"] }],
      count: 1,
    });
    renderApp();
    const card = await waitFor(
      () => screen.getByText("日程表").closest(".catalog-item") as HTMLElement,
    );
    expect(card.textContent).toContain("🌐 本机网络");
    expect(card.textContent).toContain("🔑 权限明细 1");
    // 细节 token 在 hover 气泡里
    expect(card.textContent).toContain("🗄️ db:own");
    expect(card.textContent).not.toContain("🌍 外部网络");
  });

  it("E2：空 permissions 显「🔒 无网络」、明细 0", async () => {
    apiMock.plugins.mockResolvedValue({
      plugins: [{ id: "calendar", permissions: [] }],
      count: 1,
    });
    renderApp();
    const card = await waitFor(
      () => screen.getByText("日程表").closest(".catalog-item") as HTMLElement,
    );
    expect(card.textContent).toContain("🔒 无网络");
    expect(card.textContent).toContain("🔑 权限明细 0");
  });

  it("E2：新对象 network=true 仅显中性「🌐 可联网」，不臆造本机/外网", async () => {
    apiMock.plugins.mockResolvedValue({
      plugins: [
        { id: "calendar", permissions: { filesystem: false, network: true, subprocess: false } },
      ],
      count: 1,
    });
    renderApp();
    const card = await waitFor(
      () => screen.getByText("日程表").closest(".catalog-item") as HTMLElement,
    );
    expect(card.textContent).toContain("🌐 可联网");
    expect(card.textContent).not.toContain("🌐 本机网络");
    expect(card.textContent).not.toContain("🌍 外部网络");
    // 气泡保留布尔原文，不丢信息
    expect(card.textContent).toContain('"network":true');
  });

  it("E2：hover 气泡含原始 permissions 数组原文", async () => {
    apiMock.plugins.mockResolvedValue({
      plugins: [{ id: "calendar", permissions: ["db:own", "bridge:read"] }],
      count: 1,
    });
    renderApp();
    const card = await waitFor(
      () => screen.getByText("日程表").closest(".catalog-item") as HTMLElement,
    );
    expect(card.textContent).toContain('["db:own","bridge:read"]');
    expect(card.textContent).toContain("🔑 权限明细 2");
  });

  it("E2：非 plugin 源（manual）不渲染权限行", async () => {
    renderApp();
    await waitFor(() => expect(screen.getByText("日程表")).toBeTruthy());
    const pluginCard = screen.getByText("日程表").closest(".catalog-item") as HTMLElement;
    const manualCard = screen.getByText("我的 API").closest(".catalog-item") as HTMLElement;
    expect(pluginCard.querySelector(".catalog-perms")).toBeTruthy();
    expect(manualCard.querySelector(".catalog-perms")).toBeFalsy();
  });
});
