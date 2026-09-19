/**
 * 日记前端测试：月历渲染 / 页签切换 / 随手记按钮 / 归纳按钮。
 * 网络层全部 mock，不打真实后端。
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import DiaryApp from "./DiaryApp";
import DateNavigator from "./DateNavigator";

const mocks = vi.hoisted(() => ({
  todayEntry: {
    node_id: "d-today",
    path: "日记/2026/09/2026-09-19",
    exists: true,
    date: "2026-09-19",
  },
  detail: {
    id: "d-today",
    parent_id: "m",
    kind: "doc",
    name: "2026-09-19",
    sort: 0,
    meta_json: { diary_date: "2026-09-19" },
    created_at: "2026-09-19T00:00:00+00:00",
    updated_at: "2026-09-19T00:00:00+00:00",
    deleted_at: null,
    format: "md",
    body: "# 今天的日记",
  },
  inbox: {
    items: [{ id: "in1", name: "2026-09-19-2001", created_at: "2026-09-19T12:01:00+00:00" }],
  },
}));

vi.mock("@/shared/api/events", () => ({
  usePluginEvent: () => {},
}));

vi.mock("./api", () => ({
  diaryApi: {
    today: vi.fn().mockResolvedValue(mocks.todayEntry),
    entry: vi.fn().mockResolvedValue(mocks.todayEntry),
    month: vi.fn().mockResolvedValue({ year: 2026, month: 9, days: ["2026-09-19"] }),
    inbox: vi.fn().mockResolvedValue(mocks.inbox),
    capture: vi.fn().mockResolvedValue({ node_id: "in2", path: "日记/收件箱/x", name: "x" }),
    consolidate: vi.fn().mockResolvedValue({ node_id: "in1", target_date: "2026-09-19" }),
  },
}));

vi.mock("../docs/api", () => ({
  docsApi: {
    get: vi.fn().mockResolvedValue(mocks.detail),
    saveContent: vi.fn().mockResolvedValue(mocks.detail),
    tree: vi.fn().mockResolvedValue([]),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
    trash: vi.fn(),
    restore: vi.fn(),
    purge: vi.fn(),
    revisions: vi.fn(),
    restoreRevision: vi.fn(),
    search: vi.fn(),
  },
}));

function wrap(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("DateNavigator", () => {
  it("月历高亮已有日记", () => {
    wrap(<DateNavigator year={2026} month={9} days={["2026-09-19"]} onSelect={() => {}} />);
    expect(screen.getByText("2026 年 9 月")).toBeTruthy();
    const day = screen.getByText("19");
    expect(day.className).toContain("has-entry");
  });

  it("翻月按钮回调", () => {
    const onShift = vi.fn();
    wrap(<DateNavigator year={2026} month={9} days={[]} onShift={onShift} />);
    fireEvent.click(screen.getByLabelText("上一月"));
    expect(onShift).toHaveBeenCalledWith(-1);
  });
});

describe("DiaryApp", () => {
  it("页签：默认日记 + 收件箱", () => {
    wrap(<DiaryApp />);
    expect(screen.getByText("日记")).toBeTruthy();
    expect(screen.getByText(/收件箱/)).toBeTruthy();
    expect(screen.getByText("⚡ 随手记")).toBeTruthy();
  });

  it("默认定位到当天并渲染正文", async () => {
    wrap(<DiaryApp />);
    await waitFor(() => {
      expect(screen.getByText("# 今天的日记")).toBeTruthy();
    });
  });

  it("切到收件箱页签显示条目", async () => {
    wrap(<DiaryApp />);
    fireEvent.click(screen.getByText(/收件箱/));
    await waitFor(() => {
      expect(screen.getByText("2026-09-19-2001")).toBeTruthy();
    });
    expect(screen.getByText("归纳到今天")).toBeTruthy();
  });
});
