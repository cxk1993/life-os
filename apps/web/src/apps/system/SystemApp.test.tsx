/**
 * 系统窗判据测试（V6·主人⑫）：四页签编排 + 懒挂载 + auth 薄壳语义。
 */
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, beforeEach } from "vitest";

import SystemApp from "./SystemApp";
import { useDesktopStore } from "@/kernel/store";

describe("SystemApp（V6 系统窗四合一）", () => {
  beforeEach(() => {
    const { registerModule } = useDesktopStore.getState();
    // 默认场景：注册表无 system manifest → 组件走默认四页 fallback。
    useDesktopStore.setState({ modules: {} });
    void registerModule;
  });
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
    const page = await screen.findByTestId("system-backend-page-auth");
    expect(page.textContent).toContain("后端模块 · 仅服务");
    expect(page.textContent).not.toContain("尚未接入");
  });

  it("keep-alive：切到 auth 后切回 catalog，auth 面板仍挂载（hidden）", async () => {
    render(<SystemApp />);
    expect(screen.queryByTestId("mtab-panel-auth")).toBeNull();
    fireEvent.click(screen.getByTestId("mtab-tab-auth"));
    await screen.findByTestId("system-backend-page-auth");
    fireEvent.click(screen.getByTestId("mtab-tab-catalog"));
    await waitFor(() => {
      expect(screen.getByTestId("mtab-panel-catalog").hidden).toBe(false);
    });
    // auth 面板仍挂载（hidden），keep-alive 生效
    expect(screen.getByTestId("mtab-panel-auth").hidden).toBe(true);
  });

  it("tabs 配置面（令 78）：manifest 带 tabs 声明时按配置渲染，无 entry 页落薄壳语义", () => {
    useDesktopStore.setState({
      modules: {
        system: {
          manifest: {
            id: "system",
            name: "系统",
            version: "0.1.0",
            kind: "builtin",
            // 容器型模块 schema 落地后的声明形状（最小面）：
            tabs: [
              { key: "mcp", label: "MCP Server", entry: "mcp" },
              { key: "auth", label: "账户与鉴权" },
            ],
          },
          enabled: true,
        },
      } as unknown as ReturnType<typeof useDesktopStore.getState>["modules"],
    });
    render(<SystemApp />);
    const tabs = screen.getAllByRole("tab");
    expect(tabs).toHaveLength(2);
    expect(screen.getByTestId("mtab-tab-mcp")).toBeTruthy();
    expect(screen.getByTestId("mtab-tab-auth")).toBeTruthy();
    // 无 entry 页 = 薄壳语义，不是「尚未接入」
    fireEvent.click(screen.getByTestId("mtab-tab-auth"));
    expect(screen.getByTestId("system-backend-page-auth").textContent).toContain("后端模块 · 仅服务");
  });
});
