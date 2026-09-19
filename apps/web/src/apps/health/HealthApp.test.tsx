/** 健康插件前端测试。网络全 mock。 */
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import HealthApp from "./HealthApp";

vi.mock("./api", () => ({
  healthApi: {
    list: vi.fn().mockResolvedValue([
      {
        id: "r1",
        kind: "symptom",
        title: "头痛",
        occurred_at: new Date().toISOString(),
        severity: 2,
        note: null,
        followup_needed: false,
        followup_due: null,
      },
    ]),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
    requestFollowup: vi.fn(),
  },
}));

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <HealthApp />
    </QueryClientProvider>
  );
}

describe("HealthApp", () => {
  it("renders add form and list", async () => {
    render(wrap());
    expect(screen.getByPlaceholderText(/标题/)).toBeTruthy();
    expect(screen.getByText("记一笔")).toBeTruthy();
    expect(await screen.findByText("头痛")).toBeTruthy();
  });
});
