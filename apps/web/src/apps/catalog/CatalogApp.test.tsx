import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, fireEvent, within } from "@testing-library/react";
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

// ★ 令29：页签切换助手（名字带计数角标，用正则匹配）
function switchTab(name: RegExp) {
  fireEvent.click(screen.getByRole("tab", { name }));
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

  // ─────────── ★ 令29：内部分页 ───────────

  it("令29：五个来源页签全部渲染，默认落在插件能力页", async () => {
    renderApp();
    await waitFor(() => expect(screen.getByText("日程表")).toBeTruthy());
    for (const name of [/^插件能力/, /^内核基础/, /^网页入口/, /^手动导入/, /^AI 工具/]) {
      expect(screen.getByRole("tab", { name })).toBeTruthy();
    }
    // 默认选中插件能力页
    expect(screen.getByRole("tab", { name: /^插件能力/ }).getAttribute("aria-selected")).toBe(
      "true",
    );
    // 默认页只见 plugin 源条目，manual 条目不在当前页
    expect(screen.getByText("日程表")).toBeTruthy();
    expect(screen.queryByText("我的 API")).toBeFalsy();
  });

  it("令29：页签计数角标正确（插件1/内核0/网页0/手动1/MCP2）", async () => {
    renderApp();
    await waitFor(() => expect(screen.getByText("日程表")).toBeTruthy());
    expect(screen.getByRole("tab", { name: /^插件能力/ }).textContent).toContain("1");
    expect(screen.getByRole("tab", { name: /^内核基础/ }).textContent).toContain("0");
    expect(screen.getByRole("tab", { name: /^网页入口/ }).textContent).toContain("0");
    expect(screen.getByRole("tab", { name: /^手动导入/ }).textContent).toContain("1");
    expect(screen.getByRole("tab", { name: /^AI 工具/ }).textContent).toContain("2");
  });

  it("令29：切到手动导入页签才显示手动条目", async () => {
    renderApp();
    await waitFor(() => expect(screen.getByText("日程表")).toBeTruthy());
    switchTab(/^手动导入/);
    expect(await screen.findByText("我的 API")).toBeTruthy();
    // 切走后插件条目不在当前页
    expect(screen.queryByText("日程表")).toBeFalsy();
  });

  it("令29：空源页签显示暂无占位且页签不隐藏", async () => {
    renderApp();
    await waitFor(() => expect(screen.getByText("日程表")).toBeTruthy());
    switchTab(/^内核基础/);
    expect(await screen.findByText(/暂无（这类能力还没有条目）/)).toBeTruthy();
    switchTab(/^网页入口/);
    expect(await screen.findByText(/暂无（这类能力还没有条目）/)).toBeTruthy();
  });

  it("令29：空的手动导入页签给出引导文案", async () => {
    apiMock.getCatalog.mockResolvedValue({
      entries: [sampleCatalog.entries[0]],
      generatedAt: "2026-09-20T00:00:00Z",
      counts: { plugin: 1 },
    });
    renderApp();
    await waitFor(() => expect(screen.getByText("日程表")).toBeTruthy());
    switchTab(/^手动导入/);
    expect(await screen.findByText(/暂无手动导入的能力/)).toBeTruthy();
  });

  it("令29：点头部「+ 手动导入」自动切到手动页签并展开表单", async () => {
    renderApp();
    await waitFor(() => expect(screen.getByText("日程表")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "+ 手动导入" }));
    expect(screen.getByRole("tab", { name: /^手动导入/ }).getAttribute("aria-selected")).toBe(
      "true",
    );
    expect(screen.getByPlaceholderText("名称 *")).toBeTruthy();
    // 再点收起
    fireEvent.click(screen.getByRole("button", { name: "收起" }));
    expect(screen.queryByPlaceholderText("名称 *")).toBeFalsy();
  });

  it("令29：搜索只过滤当前条目页签", async () => {
    renderApp();
    await waitFor(() => expect(screen.getByText("日程表")).toBeTruthy());
    const input = screen.getByPlaceholderText(/搜索能力/);
    // 默认插件页搜手动条目名 → 本页无匹配
    fireEvent.change(input, { target: { value: "myapi" } });
    expect(await screen.findByText(/在本页没有匹配的能力条目/)).toBeTruthy();
    expect(screen.queryByText("日程表")).toBeFalsy();
    // 切到手动页，同一搜索词命中
    switchTab(/^手动导入/);
    expect(await screen.findByText("我的 API")).toBeTruthy();
    // 清空后插件条目仍在插件页（不串页）
    fireEvent.change(input, { target: { value: "" } });
    switchTab(/^插件能力/);
    expect(await screen.findByText("日程表")).toBeTruthy();
  });

  it("令29：MCP 页签内搜索过滤工具", async () => {
    renderApp();
    await waitFor(() => expect(screen.getByText("日程表")).toBeTruthy());
    switchTab(/^AI 工具/);
    // 切页后 placeholder 变为 AI 工具语义
    const input = screen.getByPlaceholderText(/搜索 AI 工具/);
    const panel = screen.getByRole("tabpanel");
    await waitFor(() => expect(panel.textContent).toContain("calendar.event.write"));
    fireEvent.change(input, { target: { value: "todo" } });
    await waitFor(() => {
      expect(panel.textContent).toContain("todo.item.create");
      expect(panel.textContent).not.toContain("calendar.event.write");
    });
  });

  // ─────────── 原有交互（适配页签后回归） ───────────

  it("手动条目可切换开关", async () => {
    apiMock.updateManual.mockResolvedValue({
      ...sampleCatalog.entries[1],
      enabled: false,
    });
    renderApp();
    await waitFor(() => expect(screen.getByText("日程表")).toBeTruthy());
    switchTab(/^手动导入/);
    const item = await screen.findByText("我的 API");
    const toggle = within(item.closest(".catalog-item") as HTMLElement).getByTitle("点击停用");
    fireEvent.click(toggle);
    await waitFor(() =>
      expect(apiMock.updateManual).toHaveBeenCalledWith("manual-abc", { enabled: false }),
    );
  });

  it("手动条目可删除", async () => {
    apiMock.deleteManual.mockResolvedValue(undefined);
    renderApp();
    await waitFor(() => expect(screen.getByText("日程表")).toBeTruthy());
    switchTab(/^手动导入/);
    const item = await screen.findByText("我的 API");
    const del = within(item.closest(".catalog-item") as HTMLElement).getByTitle("删除");
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
    fireEvent.click(screen.getByRole("button", { name: "+ 手动导入" }));
    const nameInput = await screen.findByPlaceholderText("名称 *");
    fireEvent.change(nameInput, { target: { value: "新建的 API" } });
    fireEvent.click(screen.getByRole("button", { name: "保存" }));
    await waitFor(() => expect(apiMock.createManual).toHaveBeenCalled());
  });

  it("展示 MCP 工具区块（按插件分组，迁入 AI 工具页签）", async () => {
    renderApp();
    await waitFor(() => expect(screen.getByText("日程表")).toBeTruthy());
    // 默认插件页不见 MCP 表格
    expect(document.querySelectorAll(".catalog-mcp-table tbody tr").length).toBe(0);
    switchTab(/^AI 工具/);
    const panel = screen.getByRole("tabpanel");
    await waitFor(() => {
      expect(panel.querySelectorAll(".catalog-mcp-table tbody tr").length).toBe(2);
    });
    expect(panel.textContent).toContain("calendar.event.write");
    expect(panel.textContent).toContain("todo.item.create");
    expect(panel.textContent).toContain("写入日程事件");
  });

  it("MCP 工具列表为空时显示 provides 引导", async () => {
    apiMock.mcpTools.mockResolvedValue([]);
    renderApp();
    await waitFor(() => expect(screen.getByText("日程表")).toBeTruthy());
    switchTab(/^AI 工具/);
    expect(await screen.findByText(/当前没有插件声明 provides/)).toBeTruthy();
  });

  // ─────────── ★ E2 权限徽标（令21 五个用例，plugin 默认页可见） ───────────

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
    const pluginCard = await waitFor(
      () => screen.getByText("日程表").closest(".catalog-item") as HTMLElement,
    );
    expect(pluginCard.querySelector(".catalog-perms")).toBeTruthy();
    switchTab(/^手动导入/);
    const manualCard = (await screen.findByText("我的 API")).closest(
      ".catalog-item",
    ) as HTMLElement;
    expect(manualCard.querySelector(".catalog-perms")).toBeFalsy();
  });
});
