/**
 * BeeCount 同步面板前端测试（T08B）。
 * 网络层全部 vi.mock 后端 api，不直连 BeeCount、不接触真实 PAT。
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import BeeCountSyncPanel from "./BeeCountSyncPanel";
import type { BeeCountSource, FinanceSnapshotList, SnapshotSyncResult } from "./api";

const sourceReady: BeeCountSource = {
  upstream: "mock",
  configured: true,
  base_url_configured: true,
  token_present: false,
  last_sync: "2026-09-18T04:00:00+00:00",
  last_snapshot_date: "2026-09-18",
  snapshot_count: 1,
  write_enabled: false,
  read_tools: ["get_ledger_stats", "get_analytics_summary"],
  mcp_path: "/api/v1/mcp",
};

const snapList: FinanceSnapshotList = {
  items: [
    {
      id: "s1",
      date: "2026-09-18",
      total_asset: 1234567,
      cash: 0,
      invest: 0,
      debt: 0,
      meta: { upstream: "mock" },
      created_at: "2026-09-18T04:00:00+00:00",
      updated_at: "2026-09-18T04:00:00+00:00",
    },
  ],
  total: 1,
  limit: 5,
  offset: 0,
};

const syncResult: SnapshotSyncResult = {
  ok: true,
  upstream: "mock",
  snapshot: snapList.items[0],
};

const mockSource = vi.hoisted(() => vi.fn());
const mockSnapshots = vi.hoisted(() => vi.fn());
const mockSync = vi.hoisted(() => vi.fn());

vi.mock("./api", async () => {
  const actual = await vi.importActual<typeof import("./api")>("./api");
  return {
    ...actual,
    financeApi: {
      list: vi.fn(),
      create: vi.fn(),
      update: vi.fn(),
      remove: vi.fn(),
      summary: vi.fn(),
      snapshots: mockSnapshots,
      syncSnapshots: mockSync,
      beeCountSource: mockSource,
    },
  };
});

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
  mockSource.mockResolvedValue({ ...sourceReady });
  mockSnapshots.mockResolvedValue({ ...snapList });
  mockSync.mockResolvedValue({ ok: true, upstream: "mock", snapshot: null });
});

describe("BeeCountSyncPanel", () => {
  it("展示 upstream、最近同步与手动同步按钮", async () => {
    render(<BeeCountSyncPanel />, { wrapper: makeWrapper() });

    await waitFor(() => {
      expect(screen.getByTestId("bc-upstream").textContent).toBe("mock");
      expect(screen.getByTestId("bc-status").textContent).toBe("已就绪");
    });
    expect(screen.getByTestId("bc-total-asset").textContent).toBe("12345.67");
    expect(screen.getByTestId("bc-snap-date").textContent).toBe("2026-09-18");
    expect(screen.getByRole("button", { name: "手动同步" })).toBeTruthy();
  });

  it("点击手动同步调用后端 syncSnapshots（不直连 BeeCount）", async () => {
    mockSync.mockResolvedValue(syncResult);

    render(<BeeCountSyncPanel />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByTestId("bc-status").textContent).toBe("已就绪");
    });

    const btn = screen.getByTestId("bc-sync-btn") as HTMLButtonElement;
    expect(btn.disabled).toBe(false);

    await act(async () => {
      fireEvent.click(btn);
    });

    await waitFor(() => {
      expect(mockSync).toHaveBeenCalledTimes(1);
    });
    await waitFor(() => {
      expect(screen.getByTestId("bc-sync-ok").textContent).toContain("2026-09-18");
    });
  });

  it("未配置凭据时显示明确提示而不是空白", async () => {
    mockSource.mockResolvedValue({
      ...sourceReady,
      upstream: "mcp",
      configured: false,
      token_present: false,
      last_sync: null,
    });
    mockSnapshots.mockResolvedValue({ items: [], total: 0, limit: 5, offset: 0 });

    render(<BeeCountSyncPanel />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByTestId("bc-status").textContent).toContain("未配置");
    });
    expect(screen.getByTestId("bc-last-sync").textContent).toBe("从未同步");
  });

  it("同步失败时显示错误提示（不白屏）", async () => {
    mockSync.mockRejectedValue(new Error("上游不可达"));

    render(<BeeCountSyncPanel />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByTestId("bc-status").textContent).toBe("已就绪");
    });

    await act(async () => {
      fireEvent.click(screen.getByTestId("bc-sync-btn"));
    });

    await waitFor(() => {
      expect(screen.getByTestId("bc-sync-error").textContent).toContain("同步失败");
    });
  });
});
