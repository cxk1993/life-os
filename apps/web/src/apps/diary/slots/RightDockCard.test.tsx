/**
 * U3 右栏 · 「日历」融合卡单测（2026-09-27 · 主人报障回归）
 *
 * 主人原报障：「右侧栏的『日记 · 复盘』融合日历，点击打不开复盘，只能打开日记」。
 * 根因：旧版日期格子是纯 `<span>`，**根本没绑点击**（点不动），
 *       只有下面两行按钮能点，且都只 openWindow。
 *
 * 本测钉住修复后的契约：
 *   ① 每个日期格都是 `<button>`（可点）；
 *   ② 点某天 → 选中该天（带 is-selected）；
 *   ③ 选中日四源分区标题可点 → openWindow 到对应窗口（含 **review**）。
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import RightDockCard from "./RightDockCard";

const openWindow = vi.fn();

vi.mock("../../../kernel/store", () => ({
  useDesktopStore: (sel: (s: { openWindow: typeof openWindow }) => unknown) =>
    sel({ openWindow }),
}));

vi.mock("@/shared/api/client", () => {
  class ApiError extends Error {
    status: number;
    detail = "";
    title = "";
    constructor(status: number) {
      super(`http ${status}`);
      this.status = status;
    }
  }
  return {
    ApiError,
    api: {
      get: vi.fn((url: string) => {
        if (url.includes("/day-dots")) {
          const today = new Date();
          const key = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(
            today.getDate(),
          ).padStart(2, "0")}`;
          // 今天：日程 + 复盘都有标记（覆盖主人报障场景）
          return Promise.resolve({ [key]: ["calendar", "review"] });
        }
        if (url.includes("/day-peek")) {
          return Promise.resolve({
            date: "2026-09-27",
            list: {
              calendar: [{ id: "e1", title: "开周会", start: "2026-09-27T10:00:00+08:00" }],
              todo: [],
              diary: [{ id: "d1", title: "今天写了" }],
              review: [{ id: "r1", title: "日报已生成" }],
            },
          });
        }
        return Promise.resolve({});
      }),
    },
  };
});

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("右栏融合日历（主人报障回归）", () => {
  beforeEach(() => openWindow.mockReset());

  it("① 日期格是可点的 button（旧版是点不动的 span）", async () => {
    render(<RightDockCard />, { wrapper });
    await waitFor(() => expect(screen.getByText("日历")).toBeTruthy());
    const today = new Date();
    const ds = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(
      today.getDate(),
    ).padStart(2, "0")}`;
    const cell = await screen.findByTestId(`dock-fuse-day-${ds}`);
    expect(cell.tagName).toBe("BUTTON");
  });

  it("② 点某天 → 该格被选中（is-selected）", async () => {
    render(<RightDockCard />, { wrapper });
    const today = new Date();
    const ds = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(
      today.getDate(),
    ).padStart(2, "0")}`;
    const cell = await screen.findByTestId(`dock-fuse-day-${ds}`);
    fireEvent.click(cell);
    await waitFor(() => expect(cell.className).toContain("is-selected"));
  });

  it("③ 四源分区标题可点开对应窗口 —— ★ 复盘能打开（原报障点）", async () => {
    render(<RightDockCard />, { wrapper });

    // 四个分区标题（日程/待办/日记/复盘）都该在（等异步 peek 到位）
    for (const label of ["日程", "待办", "日记", "复盘"]) {
      expect(await screen.findByLabelText(`打开${label}`)).toBeTruthy();
    }

    // ★ 点「复盘」→ openWindow("review")（原先这条根本走不到）
    fireEvent.click(screen.getByLabelText("打开复盘"));
    expect(openWindow).toHaveBeenCalledWith("review");

    // 点「日记」→ openWindow("diary")
    fireEvent.click(screen.getByLabelText("打开日记"));
    expect(openWindow).toHaveBeenCalledWith("diary");
  });
});
