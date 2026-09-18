/**
 * 理财模块前端测试。网络层全部 mock，不打真实后端。
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import FinanceApp from "./FinanceApp";
import { formatCents } from "./api";
import type { FinanceEntry, FinanceList, FinanceSummary } from "./api";

const sample: FinanceEntry = {
  id: "f1",
  amount_cents: 1234,
  direction: "expense",
  category: "餐饮",
  account: "现金",
  occurred_at: "2026-09-15T12:00:00+08:00",
  note: "午饭",
  created_at: "2026-09-15T04:00:00+00:00",
  updated_at: "2026-09-15T04:00:00+00:00",
};

const summary: FinanceSummary = {
  date_from: null,
  date_to: null,
  expense_cents: 1384,
  income_cents: 10000,
  net_cents: 8616,
  count: 3,
  by_category: [
    { category: "餐饮", expense_cents: 1334, income_cents: 0, count: 2 },
  ],
};

const emptyList: FinanceList = { items: [], total: 0, limit: 50, offset: 0 };
const sampleList: FinanceList = {
  items: [sample],
  total: 1,
  limit: 50,
  offset: 0,
};

vi.mock("@/shared/api/events", () => ({
  usePluginEvent: () => {},
}));

vi.mock("./api", async () => {
  const actual = await vi.importActual<typeof import("./api")>("./api");
  return {
    ...actual,
    financeApi: {
      list: vi.fn().mockResolvedValue({
        items: [],
        total: 0,
        limit: 50,
        offset: 0,
      }),
      create: vi.fn().mockResolvedValue({ id: "new", amount_cents: 100 }),
      update: vi.fn(),
      remove: vi.fn().mockResolvedValue(undefined),
      summary: vi.fn().mockResolvedValue({
        date_from: null,
        date_to: null,
        expense_cents: 0,
        income_cents: 0,
        net_cents: 0,
        count: 0,
        by_category: [],
      }),
      snapshots: vi.fn().mockResolvedValue({ items: [], total: 0, limit: 5, offset: 0 }),
      syncSnapshots: vi.fn().mockResolvedValue({ ok: true, upstream: "mock", snapshot: null }),
      beeCountSource: vi.fn().mockResolvedValue({
        upstream: "mock",
        configured: true,
        base_url_configured: true,
        token_present: false,
        last_sync: null,
        last_snapshot_date: null,
        snapshot_count: 0,
        write_enabled: false,
        read_tools: ["get_ledger_stats", "get_analytics_summary"],
        mcp_path: "/api/v1/mcp",
      }),
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
});

describe("formatCents", () => {
  it("精确格式化整数分", () => {
    expect(formatCents(0)).toBe("0.00");
    expect(formatCents(1)).toBe("0.01");
    expect(formatCents(1234)).toBe("12.34");
    expect(formatCents(10000)).toBe("100.00");
    expect(formatCents(10000, "income")).toBe("+100.00");
    expect(formatCents(-8616)).toBe("-86.16");
  });
});

describe("FinanceApp 冒烟", () => {
  it("挂载显示 BeeCount 同步面板、summary 卡、快速记一笔与空态", async () => {
    render(<FinanceApp />, { wrapper: makeWrapper() });
    expect(screen.getByLabelText("BeeCount 同步")).toBeTruthy();
    expect(screen.getByLabelText("收支汇总")).toBeTruthy();
    expect(screen.getByLabelText("快速记一笔")).toBeTruthy();
    expect(screen.getByRole("button", { name: "记一笔" })).toBeTruthy();
    await waitFor(() => {
      expect(screen.getByText("还没有流水")).toBeTruthy();
    });
  });

  it("summary mock 数据渲染到卡片", async () => {
    const { financeApi } = await import("./api");
    vi.mocked(financeApi.summary).mockResolvedValue(summary);
    render(<FinanceApp />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByTestId("sum-expense").textContent).toBe("13.84");
      expect(screen.getByTestId("sum-income").textContent).toBe("100.00");
      expect(screen.getByTestId("sum-net").textContent).toBe("86.16");
    });
  });

  it("输入金额后提交 create（元→分）", async () => {
    const { financeApi } = await import("./api");
    vi.mocked(financeApi.create).mockResolvedValue({
      ...sample,
      id: "new",
      amount_cents: 1234,
    });
    render(<FinanceApp />, { wrapper: makeWrapper() });

    fireEvent.change(screen.getByLabelText("金额"), {
      target: { value: "12.34" },
    });
    fireEvent.change(screen.getByLabelText("分类"), {
      target: { value: "餐饮" },
    });
    fireEvent.change(screen.getByLabelText("账户"), {
      target: { value: "现金" },
    });
    fireEvent.click(screen.getByRole("button", { name: "记一笔" }));

    await waitFor(() => {
      expect(financeApi.create).toHaveBeenCalledWith(
        expect.objectContaining({
          direction: "expense",
          amount_cents: 1234,
          category: "餐饮",
          account: "现金",
        }),
      );
    });
  });

  it("非法金额时提交按钮禁用", () => {
    render(<FinanceApp />, { wrapper: makeWrapper() });
    const btn = screen.getByRole("button", { name: "记一笔" }) as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("金额"), { target: { value: "abc" } });
    expect(btn.disabled).toBe(true);
  });
});

describe("列表与过滤", () => {
  it("渲染流水行与金额", async () => {
    const { financeApi } = await import("./api");
    vi.mocked(financeApi.list).mockResolvedValue(sampleList);
    render(<FinanceApp />, { wrapper: makeWrapper() });
    await waitFor(() => {
      // 分类名同时出现在筛选下拉里，用备注定位列表行
      expect(screen.getByText("午饭")).toBeTruthy();
    });
    expect(screen.getByTestId("row-amount").textContent).toBe("12.34");
  });

  it("按方向筛选触发 list 参数", async () => {
    const { financeApi } = await import("./api");
    vi.mocked(financeApi.list).mockResolvedValue(emptyList);
    render(<FinanceApp />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(financeApi.list).toHaveBeenCalled();
    });
    fireEvent.change(screen.getByLabelText("按方向筛选"), {
      target: { value: "income" },
    });
    await waitFor(() => {
      expect(financeApi.list).toHaveBeenCalledWith(
        expect.objectContaining({ direction: "income" }),
      );
    });
  });

  it("删除按钮调用 remove", async () => {
    const { financeApi } = await import("./api");
    vi.mocked(financeApi.list).mockResolvedValue(sampleList);
    render(<FinanceApp />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByText("午饭")).toBeTruthy();
    });
    fireEvent.click(screen.getByRole("button", { name: "删除流水" }));
    await waitFor(() => {
      expect(financeApi.remove).toHaveBeenCalledWith("f1");
    });
  });
});
