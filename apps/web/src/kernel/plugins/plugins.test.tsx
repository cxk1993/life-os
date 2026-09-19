import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import type { ComponentType } from "react";

import { SlotHost } from "../slots/SlotHost";
import {
  clearContributions,
  contributionsForSlot,
  registerContributions,
  unregisterContributions,
} from "../slots/contributions";
import { PluginProvider } from "./PluginContext";
import { syncPluginsToStore } from "./PluginRegistry";
import { makeWorkspace, useDesktopStore } from "../store";
import type { PluginInfo, SlotName } from "./types";

function resetStore(): void {
  localStorage.clear();
  useDesktopStore.setState({
    modules: {},
    windows: [],
    workspaces: [makeWorkspace(1)],
    activeWorkspaceId: "ws1",
  });
  // ★ 插槽贡献注册表是模块级 Map，必须一起清 —— 否则上一个测试登记的组件会残留
  //   到下一个测试里（实测踩过：报错组件盖住本测试组件，表现为"找不到文本"）。
  clearContributions();
}

function registerDemo(id: string, slots: SlotName[]): void {
  useDesktopStore.getState().registerModule({
    id,
    name: id,
    version: "0.1.0",
    kind: "builtin",
    entry: "",
    window: { w: 400, h: 300 },
    slots,
  });
}

describe("前端插件框架（T14）", () => {
  beforeEach(() => {
    resetStore();
  });
  afterEach(() => {
    cleanup();
    unregisterContributions("demo");
    unregisterContributions("rogue");
    unregisterContributions("boom");
  });

  it("SlotHost 渲染某扩展点的贡献组件（UI 实际显示卡片）", () => {
    registerDemo("demo", ["dashboard.card"]);
    registerContributions("demo", [
      { slot: "dashboard.card", pluginId: "demo", component: () => <div>你好，卡片</div> },
    ]);
    render(<SlotHost slot="dashboard.card" />);
    expect(screen.getByText("你好，卡片")).toBeTruthy();
  });

  it("插件禁用后其扩展点贡献不再渲染（启用态随 store 实时变化）", () => {
    registerDemo("demo", ["dashboard.card"]);
    registerContributions("demo", [
      { slot: "dashboard.card", pluginId: "demo", component: () => <div>你好，卡片</div> },
    ]);
    expect(contributionsForSlot("dashboard.card")).toHaveLength(1);
    render(<SlotHost slot="dashboard.card" />);
    expect(screen.getByText("你好，卡片")).toBeTruthy();

    cleanup();
    useDesktopStore.getState().disableModule("demo");
    expect(contributionsForSlot("dashboard.card")).toHaveLength(0);
    render(<SlotHost slot="dashboard.card" />);
    expect(screen.queryByText("你好，卡片")).toBeNull();
  });

  it("贡献声明了未出现在 manifest.slots 的扩展点时被忽略（越权不挂载）", () => {
    registerDemo("rogue", ["desktop.widget"]);
    registerContributions("rogue", [
      { slot: "dashboard.card", pluginId: "rogue", component: () => <div>越权卡片</div> },
    ]);
    expect(contributionsForSlot("dashboard.card")).toHaveLength(0);
  });

  it("插件组件抛错被 PluginBoundary 兜住，桌面不白屏", () => {
    registerDemo("boom", ["dashboard.card"]);
    registerContributions("boom", [
      {
        slot: "dashboard.card",
        pluginId: "boom",
        component: () => {
          throw new Error("炸了");
        },
      },
    ]);
    render(<SlotHost slot="dashboard.card" />);
    expect(screen.getByText(/渲染失败/)).toBeTruthy();
  });

  it("syncPluginsToStore 把后端插件同步进桌面 store（Dock 可读到、禁用即置灰）", () => {
    const plugins: PluginInfo[] = [
      {
        id: "a",
        name: "甲",
        version: "0.1.0",
        kind: "builtin",
        enabled: true,
        source: "builtin",
        manifest: {
          id: "a",
          name: "甲",
          version: "0.1.0",
          kind: "builtin",
          entry: "",
          window: { w: 480, h: 320 },
          slots: [],
        },
      },
      {
        id: "b",
        name: "乙",
        version: "0.1.0",
        kind: "third-party",
        enabled: false,
        source: "third-party",
        manifest: {
          id: "b",
          name: "乙",
          version: "0.1.0",
          kind: "third-party",
          entry: "",
          window: { w: 480, h: 320 },
          slots: [],
        },
      },
    ];
    syncPluginsToStore(plugins);
    expect(useDesktopStore.getState().modules["a"]?.enabled).toBe(true);
    expect(useDesktopStore.getState().modules["b"]?.enabled).toBe(false);
  });

  it("PluginProvider 拉取插件并挂载插槽贡献（集成：UI 实际显示 + 注册进 store）", async () => {
    const fakeClient = {
      get: vi.fn(async () => ({
        plugins: [
          {
            id: "demo",
            name: "演示",
            version: "0.1.0",
            kind: "builtin",
            enabled: true,
            source: "builtin",
            manifest: {
              id: "demo",
              name: "演示",
              version: "0.1.0",
              kind: "builtin",
              entry: "@/apps/demo",
              window: { w: 480, h: 320 },
              slots: ["dashboard.card"],
            },
          },
        ],
      })),
      post: vi.fn(async () => ({ ok: true })),
    };
    const fakeLoad = async () =>
      ({ default: { slots: { "dashboard.card": () => <div>Provider 卡片</div> } } }) as unknown as {
        default: { slots?: Partial<Record<SlotName, ComponentType>> };
      };

    render(
      <PluginProvider client={fakeClient as never} loadEntry={fakeLoad}>
        <SlotHost slot="dashboard.card" />
      </PluginProvider>,
    );

    await waitFor(() => expect(screen.getByText("Provider 卡片")).toBeTruthy());
    // 贡献确实进了插槽注册表（不是靠恰好在别的路径上渲染出来的）
    expect(contributionsForSlot("dashboard.card")).toHaveLength(1);
    // 插件已注册进桌面 store（Dock 即可显示/置灰）
    expect(useDesktopStore.getState().modules["demo"]).toBeTruthy();
    expect(fakeClient.get).toHaveBeenCalledWith("/api/v1/plugins");
  });
});
