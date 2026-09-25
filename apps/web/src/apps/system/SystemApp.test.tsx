/**
 * 系统窗判据测试（V6·主人⑫）：四页签编排 + 懒挂载 + auth 薄壳语义。
 */
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import SystemApp from "./SystemApp";

describe("SystemApp（V6 系统窗四合一）", () => {
  it("渲染四个一级页签：能力目录/MCP/推送/账户与鉴权", () => {
    render(<SystemApp />);
    const tabs = screen.getAllByRole("tab");
    expect(tabs).toHaveLength(4);
    expect(screen.getByTestId("mtab-tab-catalog")).toBeTruthy();
    expect(screen.getByTestId("mtab-tab-mcp")).toBeTruthy();
    expect(screen.getByTestId("mtab-tab-push")).toBeTruthy();
    expect(screen.getByTestId("mtab-tab-auth")).toBeTruthy();
    expect(screen.getByTestId("mtab-tab-catalog").getAttribute("aria-selected")).toBe("true");
  });

  it("auth 页为「后端模块 · 仅服务」薄壳语义（V5 口径，非「尚未接入」）", async () => {
    render(<SystemApp />);
    fireEvent.click(screen.getByTestId("mtab-tab-auth"));
    const page = await screen.findByTestId("system-auth-page");
    expect(page.textContent).toContain("后端模块 · 仅服务");
    expect(page.textContent).not.toContain("尚未接入");
  });

  it("懒挂载：初始只挂 catalog 页，切到 auth 后 keep-alive 切回", async () => {
    render(<SystemApp />);
    expect(screen.queryByTestId("mtab-panel-auth")).toBeNull();
    fireEvent.click(screen.getByTestId("mtab-tab-auth"));
    await screen.findByTestId("system-auth-page");
    fireEvent.click(screen.getByTestId("mtab-tab-catalog"));
    await waitFor(() => {
      expect(screen.getByTestId("mtab-panel-catalog").hidden).toBe(false);
    });
    // auth 面板仍挂载（hidden），keep-alive 生效
    expect(screen.getByTestId("mtab-panel-auth").hidden).toBe(true);
  });
});
