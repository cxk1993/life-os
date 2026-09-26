/**
 * U3 右栏日期口径回归判据（Qoder 侦察 09-26：calendar/events 要 tz-aware，
 * date-only 一律 422——U3 重写曾误传致「暂时不可用」上产）。
 * 断言：listRange 收到的 from/to 必须带 +08:00（formatSH 形态），且 to 为次月 1 日
 * （开区间语义下保证月末事件不缺）。
 */
import { render } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import RightDockCard from "./RightDockCard";
import { calendarApi } from "../api";

vi.mock("../api", () => ({
  calendarApi: { listRange: vi.fn(async () => []) },
}));

vi.mock("../../../kernel/store", () => ({
  useDesktopStore: (sel: (s: { openWindow: () => void }) => unknown) =>
    sel({ openWindow: () => {} }),
}));

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("RightDockCard 日期口径（回归）", () => {
  beforeEach(() => {
    vi.mocked(calendarApi.listRange).mockReset();
    vi.mocked(calendarApi.listRange).mockResolvedValue([]);
  });

  it("from/to 必须是 tz-aware（含 +08:00），to 为次月 1 日（开区间不缺月末）", async () => {
    render(<RightDockCard />, { wrapper });

    await vi.waitFor(() => {
      expect(calendarApi.listRange).toHaveBeenCalled();
    });
    const [from, to] = vi.mocked(calendarApi.listRange).mock.calls[0] as [string, string];
    expect(from).toMatch(/\+08:00$/);
    expect(to).toMatch(/\+08:00$/);
    // to = 次月 1 日（开区间语义：本月末最后一天事件不缺），且时序在 from 之后
    expect(to.slice(8, 10)).toBe("01");
    expect(new Date(to).getTime()).toBeGreaterThan(new Date(from).getTime());
  });
});
