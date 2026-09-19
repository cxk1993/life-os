/**
 * 人格体系前端测试：薄壳冒烟 + 复用 T15 组件 + 自动建根。
 * 网络层全部 mock，不打真实后端。
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import PersonaApp from "./PersonaApp";
import { docsApi } from "../docs/api";

const mocks = vi.hoisted(() => ({
  emptyTree: [] as unknown[],
  rootNode: {
    id: "p-root",
    parent_id: null,
    kind: "folder",
    name: "人格体系",
    sort: 0,
    meta_json: null,
    created_at: "2026-09-19T00:00:00+00:00",
    updated_at: "2026-09-19T00:00:00+00:00",
    deleted_at: null,
    children: [],
  },
  treeWithRoot: [
    {
      id: "p-root",
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
          id: "p-doc",
          parent_id: "p-root",
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
}));

vi.mock("@/shared/api/events", () => ({
  usePluginEvent: () => {},
}));

vi.mock("../docs/api", () => ({
  docsApi: {
    tree: vi.fn(),
    create: vi.fn(),
    get: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
    saveContent: vi.fn(),
    search: vi.fn(),
    trash: vi.fn(),
    restore: vi.fn(),
    purge: vi.fn(),
    revisions: vi.fn(),
    restoreRevision: vi.fn(),
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
  (docsApi.tree as ReturnType<typeof vi.fn>).mockResolvedValue(mocks.emptyTree);
  (docsApi.create as ReturnType<typeof vi.fn>).mockResolvedValue(mocks.rootNode);
  (docsApi.search as ReturnType<typeof vi.fn>).mockResolvedValue({ items: [], next_cursor: null });
});

describe("PersonaApp", () => {
  it("标题渲染", () => {
    wrap(<PersonaApp />);
    expect(screen.getByText("🧠 人格体系")).toBeTruthy();
  });

  it("空森林时自动创建人格根", async () => {
    wrap(<PersonaApp />);
    await waitFor(() => {
      expect(docsApi.create).toHaveBeenCalledWith(
        expect.objectContaining({ kind: "folder", name: "人格体系" }),
      );
    });
  });

  it("有人格根时渲染树节点（复用 T15 DocsTree）", async () => {
    (docsApi.tree as ReturnType<typeof vi.fn>).mockResolvedValue(mocks.treeWithRoot);
    (docsApi.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: "p-doc",
      parent_id: "p-root",
      kind: "doc",
      name: "价值观",
      format: "md",
      body: "# 我的价值观",
      created_at: "2026-09-19T00:00:00+00:00",
      updated_at: "2026-09-19T00:00:00+00:00",
      deleted_at: null,
    });
    wrap(<PersonaApp />);
    await waitFor(() => {
      expect(screen.getByText("价值观")).toBeTruthy();
    });
  });

  // ───────── BUG-T16-1 回归测试 ─────────
  it("★ 空森林连续挂载 N 次只创建 1 个根（挂载幂等）", async () => {
    // 模拟连续挂载：每次 tree 都返回空（第一次查询可能还没完成）
    (docsApi.tree as ReturnType<typeof vi.fn>).mockResolvedValue(mocks.emptyTree);
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });

    // 挂载 - 卸载 - 再挂载，模拟切走切回
    const first = render(
      <QueryClientProvider client={qc}>
        <PersonaApp />
      </QueryClientProvider>,
    );
    await waitFor(() => {
      expect(docsApi.create).toHaveBeenCalledTimes(1);
    });
    first.unmount();

    // 第二次挂载：tree 仍空（create 成功后 invalidate 但 mock 仍返回空）
    render(
      <QueryClientProvider client={qc}>
        <PersonaApp />
      </QueryClientProvider>,
    );
    await waitFor(() => {
      // 关键断言：create 只被调用 1 次（第二次挂载应复用已有根，不重复创建）
      expect(docsApi.create).toHaveBeenCalledTimes(1);
    });
  });

  it("★ 存在重复根时启动对账：保正根、其余软删", async () => {
    const dupTree = [
      { ...mocks.rootNode, id: "p-root-1", meta_json: { slug: "root:persona" } },
      { ...mocks.rootNode, id: "p-root-2", meta_json: null },
      { ...mocks.rootNode, id: "p-root-3", meta_json: null },
    ];
    (docsApi.tree as ReturnType<typeof vi.fn>).mockResolvedValue(dupTree);
    (docsApi.remove as ReturnType<typeof vi.fn>).mockResolvedValue(undefined);
    wrap(<PersonaApp />);
    await waitFor(() => {
      // 保留带 slug 的正根 p-root-1，软删 p-root-2 / p-root-3
      expect(docsApi.remove).toHaveBeenCalledTimes(2);
    });
    const removedIds = (docsApi.remove as ReturnType<typeof vi.fn>).mock.calls.map((c) => c[0]);
    expect(removedIds).toContain("p-root-2");
    expect(removedIds).toContain("p-root-3");
    expect(removedIds).not.toContain("p-root-1");
  });
});
