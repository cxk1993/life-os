/**
 * C′ 里程碑侧栏卡测试：三态降级（数据 / 404=countdown 未装 / 空列表）。
 * 网络层全 mock（@/shared/api/client 的 api.get），不打真实后端。
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { ApiError } from "@/shared/api/client";
import LandmarksSidecar from "./LandmarksSidecar";
import type { Landmark } from "./LandmarksSidecar";

vi.mock("@/shared/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/shared/api/client")>("@/shared/api/client");
  return { ...actual, api: { get: vi.fn() } };
});

import { api } from "@/shared/api/client";

function wrapper(): { el: ReactNode } {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return {
    el: (
      <QueryClientProvider client={qc}>
        <LandmarksSidecar />
      </QueryClientProvider>
    ),
  };
}

const landmarks: Landmark[] = [
  {
    id: "a1",
    title: "唤醒日",
    kind: "anniversary",
    on_date: "2027-06-27",
    days_until: 277,
    note: "",
  },
  { id: "a2", title: "远期目标", kind: "countdown", days_until: 800 },
];

describe("C′ · 里程碑侧栏卡（LandmarksSidecar）", () => {
  beforeEach(() => {
    vi.mocked(api.get).mockReset();
  });
  afterEach(() => {
    cleanup();
  });

  it("200 有数据 → 渲染里程碑列表（天数 + 标题 + kind 标签）", async () => {
    vi.mocked(api.get).mockResolvedValue(landmarks);
    const { el } = wrapper();
    render(el);
    await waitFor(() => expect(screen.getByTestId("landmarks-sidecar")).toBeTruthy());
    expect(screen.getByText("277")).toBeTruthy();
    expect(screen.getByText(/唤醒日/)).toBeTruthy();
    expect(screen.getByText("纪念日")).toBeTruthy();
    expect(screen.getByText("800")).toBeTruthy();
    expect(screen.getByText("倒计时")).toBeTruthy();
    expect(vi.mocked(api.get)).toHaveBeenCalledWith("/api/v1/countdown/landmarks?window=365");
  });

  it("404（countdown 未安装）→ 不渲染（无幽灵卡）", async () => {
    vi.mocked(api.get).mockRejectedValue(
      new ApiError({
        type: "about:blank",
        title: "HTTP 404",
        status: 404,
        detail: "not found",
      }),
    );
    const { el } = wrapper();
    const { container } = render(el);
    await waitFor(() => expect(vi.mocked(api.get)).toHaveBeenCalled());
    // 等查询 settle 后再断言无节点
    await waitFor(() =>
      expect(container.querySelector("[data-testid='landmarks-sidecar']")).toBeNull(),
    );
  });

  it("200 空数组 → 渲染「暂无里程碑」空态", async () => {
    vi.mocked(api.get).mockResolvedValue([]);
    const { el } = wrapper();
    render(el);
    await waitFor(() => expect(screen.getByText("暂无里程碑")).toBeTruthy());
  });

  it("500（真错误）→ 不渲染（不把错误当里程碑显示）", async () => {
    vi.mocked(api.get).mockRejectedValue(
      new ApiError({
        type: "about:blank",
        title: "HTTP 500",
        status: 500,
        detail: "boom",
      }),
    );
    const { el } = wrapper();
    const { container } = render(el);
    await waitFor(() => expect(vi.mocked(api.get)).toHaveBeenCalled());
    await waitFor(() =>
      expect(container.querySelector("[data-testid='landmarks-sidecar']")).toBeNull(),
    );
  });
});
