/**
 * 待办模块前端测试：主界面冒烟 + 行渲染 + 快速添加提交。
 * 网络层全部 mock，不打真实后端。
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import TodoApp from "./TodoApp";
import ItemRow from "./ItemRow";
import QuickAdd from "./QuickAdd";
import type { TodoItem } from "./api";
import { useTodoUI } from "./state";

const sample: TodoItem = {
  id: "t1",
  text: "写周报",
  done: false,
  done_at: null,
  due_at: "2026-09-20T10:00:00+08:00",
  priority: "high",
  recur_rule: null,
  tags: ["工作"],
  source_path: null,
  source_line: null,
  sort: 0,
  series_id: "t1",
  instance_no: 0,
  created_at: "2026-09-17T00:00:00+00:00",
  updated_at: "2026-09-17T00:00:00+00:00",
};

vi.mock("@/shared/api/events", () => ({
  usePluginEvent: () => {},
}));

vi.mock("./api", () => ({
  todoApi: {
    list: vi.fn().mockResolvedValue({ items: [], next_cursor: null }),
    create: vi.fn().mockResolvedValue({ id: "new", text: "x" }),
    createStructured: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
    toggle: vi.fn().mockResolvedValue({ id: "t1", done: true, done_at: "now" }),
    importMarkdown: vi.fn(),
    exportMarkdown: vi.fn(),
    summary: vi.fn().mockResolvedValue({ today: 0, overdue: 0, week_done: 0 }),
    tags: vi.fn().mockResolvedValue([]),
  },
}));

function makeWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  // ★ 2026-09-28：zustand store 是模块级的，筛选/视图会在用例之间串味 → 每例复位
  useTodoUI.setState({ filterTag: null, view: "today" });
});

describe("TodoApp 冒烟", () => {
  it("挂载不报错，显示四个视图 Tab 与快速添加框", async () => {
    render(<TodoApp />, { wrapper: makeWrapper() });
    expect(screen.getByText("今日")).toBeTruthy();
    expect(screen.getByText("全部")).toBeTruthy();
    expect(screen.getByText("周期")).toBeTruthy();
    // ★ 2026-10-02（主人令）：第三栏「归档」
    expect(screen.getByText(/^归档 \d+天$/)).toBeTruthy();
    expect(screen.getByLabelText("快速添加待办")).toBeTruthy();
  });

  it("★ 「全部」视图请求 status=active（**不含归档**）—— 归档项不该混在主列表里", async () => {
    // 主人原话：「打钩完成的日期过了 7 天，就可以自动归档、自动隐藏」。
    // 全部视图若用 status=all，几十天前打完的旧账会照旧摆在主列表 —— 正是要消除的观感。
    const { todoApi } = await import("./api");
    vi.mocked(todoApi.list).mockResolvedValue({ items: [], next_cursor: null });
    render(<TodoApp />, { wrapper: makeWrapper() });
    fireEvent.click(screen.getByText("全部"));
    await waitFor(() =>
      expect(todoApi.list).toHaveBeenCalledWith(expect.objectContaining({ status: "active" })),
    );
    // 防回退：绝不能是 all
    expect(vi.mocked(todoApi.list).mock.calls.every((c) => (c[0] as { status?: string })?.status !== "all")).toBe(
      true,
    );
  });

  it("★ 「归档」Tab 请求 status=archived", async () => {
    const { todoApi } = await import("./api");
    vi.mocked(todoApi.list).mockResolvedValue({ items: [], next_cursor: null });
    render(<TodoApp />, { wrapper: makeWrapper() });
    fireEvent.click(screen.getByText(/^归档 \d+天$/));
    await waitFor(() =>
      expect(todoApi.list).toHaveBeenCalledWith(expect.objectContaining({ status: "archived" })),
    );
  });

  it("切换到「全部」Tab 渲染 AllView 空态", async () => {
    render(<TodoApp />, { wrapper: makeWrapper() });
    fireEvent.click(screen.getByText("全部"));
    await waitFor(() => {
      expect(screen.getByText("还没有任何待办")).toBeTruthy();
    });
  });
});

describe("ItemRow", () => {
  it("渲染文本、标签、优先级与截止日期", () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <ItemRow item={sample} />
      </QueryClientProvider>,
    );
    expect(screen.getByText("写周报")).toBeTruthy();
    expect(screen.getByText("#工作")).toBeTruthy();
    expect(screen.getByText("高")).toBeTruthy();
    expect(screen.getByText(/9-20/)).toBeTruthy();
  });

  it("勾选框点击触发 toggle", async () => {
    const { todoApi } = await import("./api");
    render(
      <QueryClientProvider client={new QueryClient()}>
        <ItemRow item={sample} />
      </QueryClientProvider>,
    );
    const box = screen.getByRole("button", { name: "标记为完成" });
    fireEvent.click(box);
    await waitFor(() => {
      expect(todoApi.toggle).toHaveBeenCalledWith("t1");
    });
  });
});

describe("QuickAdd", () => {
  it("空文本时提交按钮禁用", () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <QuickAdd />
      </QueryClientProvider>,
    );
    const btn = screen.getByRole("button", { name: "添加" });
    expect((btn as HTMLButtonElement).disabled).toBe(true);
  });

  it("输入后提交调用 create 并清空输入", async () => {
    const { todoApi } = await import("./api");
    render(
      <QueryClientProvider client={new QueryClient()}>
        <QuickAdd />
      </QueryClientProvider>,
    );
    const input = screen.getByLabelText("快速添加待办");
    fireEvent.change(input, { target: { value: "买牛奶 @明天 !高" } });
    fireEvent.click(screen.getByRole("button", { name: "添加" }));
    await waitFor(() => {
      expect(todoApi.create).toHaveBeenCalledWith("买牛奶 @明天 !高");
    });
    await waitFor(() => {
      expect((input as HTMLInputElement).value).toBe("");
    });
  });

  it("H4 · 提交失败显示错误提示且输入保留（不再静默）", async () => {
    const { todoApi } = await import("./api");
    vi.mocked(todoApi.create).mockRejectedValueOnce(new Error("网络不可用"));
    render(
      <QueryClientProvider client={new QueryClient()}>
        <QuickAdd />
      </QueryClientProvider>,
    );
    const input = screen.getByLabelText("快速添加待办");
    fireEvent.change(input, { target: { value: "断网也要记的待办" } });
    fireEvent.click(screen.getByRole("button", { name: "添加" }));
    await waitFor(() => {
      expect(screen.getByTestId("todo-quick-error")).toBeTruthy();
    });
    expect(screen.getByText(/保存失败：网络不可用/)).toBeTruthy();
    // 输入保留（可重试），不静默清空
    expect((input as HTMLInputElement).value).toBe("断网也要记的待办");
  });
});

  it("★ 动态标签条：数据来自 /tags，点一下筛上并切「全部」，再点取消", async () => {
    const { todoApi } = await import("./api");
    vi.mocked(todoApi.tags).mockResolvedValue([
      { tag: "学业", todo: 2, done: 1, total: 3 },
      { tag: "副业", todo: 3, done: 0, total: 3 },
    ]);
    render(<TodoApp />, { wrapper: makeWrapper() });
    // 学业由固定按钮承担 → 不进动态条（同一个筛选不给两个入口）
    await waitFor(() => expect(screen.queryByTestId("todo-tagchip-副业")).toBeTruthy());
    expect(screen.queryByTestId("todo-tagchip-学业")).toBeNull();

    // 点一下 → 筛上「副业」，并切到「全部」视图（一键查看）
    fireEvent.click(screen.getByTestId("todo-tagchip-副业"));
    await waitFor(() =>
      expect(screen.getByTestId("todo-tagchip-副业").getAttribute("aria-pressed")).toBe("true"),
    );
    expect(useTodoUI.getState().view).toBe("all");

    // 再点一下 → 取消筛选
    fireEvent.click(screen.getByTestId("todo-tagchip-副业"));
    await waitFor(() =>
      expect(screen.getByTestId("todo-tagchip-副业").getAttribute("aria-pressed")).toBe("false"),
    );
    expect(useTodoUI.getState().filterTag).toBeNull();
  });

  it("★ 行内改标签：点「＋标签」输入 `学业/高数 副业` → PATCH tags（去重保序）", async () => {
    const { todoApi } = await import("./api");
    render(<ItemRow item={sample} />, { wrapper: makeWrapper() });
    fireEvent.click(screen.getByTestId("todo-tag-add"));
    const input = screen.getByTestId("todo-tag-edit");
    fireEvent.change(input, { target: { value: "学业/高数 副业 学业/高数" } });
    fireEvent.keyDown(input, { key: "Enter" });
    await waitFor(() =>
      expect(todoApi.update).toHaveBeenCalledWith("t1", {
        tags: ["学业/高数", "副业"],
      }),
    );
  });
