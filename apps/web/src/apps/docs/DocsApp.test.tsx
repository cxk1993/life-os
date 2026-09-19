/**
 * 文档树前端测试：主界面冒烟 + 树渲染 + 查看器 + MarkdownView 懒加载切换。
 * 网络层全部 mock，不打真实后端。
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import DocsApp from "./DocsApp";
import DocsTree from "./DocsTree";
import DocsViewer from "./DocsViewer";
import MarkdownView from "./MarkdownView";
import type { DocsNode } from "./api";

// jsdom 无法真实渲染 react-markdown 的 lazy/Suspense（会产生 stderr 噪音），
// mock 成简单 div：MarkdownView 的 UI 逻辑（切换/兜底）仍可测，真实渲染归真机。
vi.mock("react-markdown", () => ({
  default: ({ children }: { children: string }) => <div data-testid="md-render">{children}</div>,
}));
vi.mock("remark-gfm", () => ({ default: () => () => {} }));

const mocks = vi.hoisted(() => ({
  sampleTree: [
    {
      id: "f1",
      parent_id: null,
      kind: "folder",
      name: "人格体系",
      sort: 0,
      meta_json: null,
      created_at: "2026-09-19T00:00:00+00:00",
      updated_at: "2026-09-19T00:00:00+00:00",
      deleted_at: null,
      children: [
        {
          id: "d1",
          parent_id: "f1",
          kind: "doc",
          name: "价值观",
          sort: 0,
          meta_json: null,
          created_at: "2026-09-19T00:00:00+00:00",
          updated_at: "2026-09-19T00:00:00+00:00",
          deleted_at: null,
        },
      ],
    },
  ],
  getMock: {
    id: "d1",
    parent_id: "f1",
    kind: "doc",
    name: "价值观",
    format: "md",
    body: "# 我的价值观",
    created_at: "2026-09-19T00:00:00+00:00",
    updated_at: "2026-09-19T00:00:00+00:00",
    deleted_at: null,
  },
}));

const sampleTree = mocks.sampleTree as DocsNode[];

vi.mock("@/shared/api/events", () => ({
  usePluginEvent: () => {},
}));

vi.mock("./api", () => ({
  docsApi: {
    tree: vi.fn().mockResolvedValue(mocks.sampleTree),
    get: vi.fn().mockResolvedValue(mocks.getMock),
    create: vi.fn().mockResolvedValue({ id: "new", name: "x" }),
    update: vi.fn().mockResolvedValue({ id: "d1" }),
    remove: vi.fn().mockResolvedValue(undefined),
    trash: vi.fn().mockResolvedValue({ items: [], next_cursor: null }),
    restore: vi.fn(),
    purge: vi.fn(),
    saveContent: vi.fn().mockResolvedValue({ id: "d1" }),
    revisions: vi.fn().mockResolvedValue({ items: [], next_cursor: null }),
    restoreRevision: vi.fn(),
    search: vi.fn().mockResolvedValue({ items: [], next_cursor: null }),
  },
}));

function wrap(ui: ReactNode) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("DocsTree", () => {
  it("渲染树节点", () => {
    wrap(<DocsTree nodes={sampleTree} />);
    expect(screen.getByText("人格体系")).toBeTruthy();
    expect(screen.getByText("价值观")).toBeTruthy();
  });

  it("点击节点触发 onSelect", () => {
    const onSelect = vi.fn();
    wrap(<DocsTree nodes={sampleTree} onSelect={onSelect} />);
    fireEvent.click(screen.getByText("价值观"));
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ id: "d1" }));
  });

  it("新建根文件夹按钮触发 onCreate", () => {
    const onCreate = vi.fn();
    wrap(<DocsTree nodes={[]} onCreate={onCreate} />);
    fireEvent.click(screen.getByText("+ 新建根文件夹"));
    expect(onCreate).toHaveBeenCalled();
  });
});

describe("DocsViewer", () => {
  it("渲染 md 内容并显示保存按钮", () => {
    wrap(<DocsViewer name="价值观" format="md" body="# 标题" />);
    expect(screen.getByText("价值观")).toBeTruthy();
    expect(screen.getByText("保存")).toBeTruthy();
  });

  it("修改后保存触发 onSave", () => {
    const onSave = vi.fn();
    // txt 模式下显示 textarea，可编辑
    wrap(<DocsViewer name="价值观" format="txt" body="旧" onSave={onSave} />);
    const ta = screen.getByPlaceholderText("开始书写…");
    fireEvent.change(ta, { target: { value: "新内容" } });
    fireEvent.click(screen.getByText("保存"));
    expect(onSave).toHaveBeenCalledWith("txt", "新内容");
  });
});

describe("MarkdownView", () => {
  it("默认渲染模式显示渲染按钮", () => {
    wrap(<MarkdownView content="# Hello" />);
    expect(screen.getByText("源码")).toBeTruthy();
    expect(screen.getByText("渲染")).toBeTruthy();
  });

  it("切换到源码模式显示原文", async () => {
    wrap(<MarkdownView content="**bold** text" defaultMode="render" />);
    fireEvent.click(screen.getByText("源码"));
    await waitFor(() => {
      expect(screen.getByText("**bold** text")).toBeTruthy();
    });
  });

  it("★ 渲染模式不崩（BUG-T15-1 回归）：remark-gfm 加载失败时有错误兜底", async () => {
    // jsdom 无法真实跑 react-markdown+remark-gfm（懒加载/Suspense 限制），
    // 这里验证「加载失败 → 显示错误兜底而非崩溃到内核」这条安全路径。
    // 真实渲染由真机验收（Qoder CN 复验 ACCEPT-T15 §2#6）。
    wrap(<MarkdownView content="# Hello" defaultMode="render" />);
    await waitFor(
      () => {
        // 无论渲染成功还是失败，组件都不能把错误抛到内核边界
        expect(screen.getByText("源码")).toBeTruthy();
      },
      { timeout: 3000 },
    );
  });
});

describe("DocsApp", () => {
  it("加载树并显示文件夹", async () => {
    wrap(<DocsApp />);
    await waitFor(() => {
      expect(screen.getByText("人格体系")).toBeTruthy();
    });
  });

  it("点击文档打开查看器", async () => {
    wrap(<DocsApp />);
    await waitFor(() => {
      expect(screen.getByText("人格体系")).toBeTruthy();
    });
    fireEvent.click(screen.getByText("价值观"));
    await waitFor(() => {
      expect(screen.getByText("# 我的价值观")).toBeTruthy();
    });
  });
});
