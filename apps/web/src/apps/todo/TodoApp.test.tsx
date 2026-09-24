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
});

describe("TodoApp 冒烟", () => {
  it("挂载不报错，显示三个视图 Tab 与快速添加框", async () => {
    render(<TodoApp />, { wrapper: makeWrapper() });
    expect(screen.getByText("今日")).toBeTruthy();
    expect(screen.getByText("全部")).toBeTruthy();
    expect(screen.getByText("周期")).toBeTruthy();
    expect(screen.getByLabelText("快速添加待办")).toBeTruthy();
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
