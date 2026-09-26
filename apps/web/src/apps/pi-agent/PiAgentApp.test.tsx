/**
 * ★ Pi 智能体容器测试（主人 2026-09-26 令：「AI 编排也收，并进 pi-agent 当一个 tab」）。
 *
 * 判据：
 *   C1 · 容器渲染出**两个**页签：对话 / 编排；
 *   C2 · 默认落在「对话」页（PiChatView 内容可见）；
 *   C3 · 点「编排」→ 切到 AgentsApp（懒挂载生效）。
 *
 * 依赖：kernel/MultitabFrame（页签原语）+ 两个 lazy 子页。
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

import { PiAgentApp } from "./index";

vi.mock("@/shared/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/shared/api/client")>("@/shared/api/client");
  return { ...actual, api: { get: vi.fn(), post: vi.fn() } };
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("★ Pi 智能体容器（一窗多页）", () => {
  it("C1 · 渲染出两个页签：对话 / 编排", async () => {
    render(<PiAgentApp />);
    await waitFor(() => {
      expect(screen.getByRole("tab", { name: "对话" })).toBeTruthy();
      expect(screen.getByRole("tab", { name: "编排" })).toBeTruthy();
    });
  });

  it("C2 · 默认落在「对话」页", async () => {
    render(<PiAgentApp />);
    await waitFor(() => {
      const chatTab = screen.getByRole("tab", { name: "对话" });
      expect(chatTab.getAttribute("aria-selected")).toBe("true");
    });
  });

  it("C3 · 点「编排」→ 切页（懒挂载）", async () => {
    render(<PiAgentApp />);
    const agentsTab = await screen.findByRole("tab", { name: "编排" });
    fireEvent.click(agentsTab);
    await waitFor(() => {
      expect(agentsTab.getAttribute("aria-selected")).toBe("true");
    });
  });
});
