import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import { SidecarSlot } from "../WindowFrame";
import { SLOTS, isSlotName, SLOT_NAMES } from "./slots";
import {
  clearContributions,
  registerContributions,
  unregisterContributions,
} from "./contributions";
import { makeWorkspace, useDesktopStore } from "../store";
import type { SlotName } from "../plugins/types";

/**
 * E5：`window.sidecar` 扩展点专项测试。
 * 判据卡 J1（slot 注册）/ J3（类型语义）/ J4（无贡献零渲染）/ J5（attachTo 过滤）/ J6（缺省全窗）。
 */

function resetStore(): void {
  localStorage.clear();
  useDesktopStore.setState({
    modules: {},
    windows: [],
    workspaces: [makeWorkspace(1)],
    activeWorkspaceId: "ws1",
  });
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

describe("E5 · window.sidecar 窗口侧栏扩展点", () => {
  beforeEach(() => {
    resetStore();
  });
  afterEach(() => {
    cleanup();
    unregisterContributions("demo");
    unregisterContributions("global");
  });

  it("J1 · SLOTS 注册了 13 号扩展点 window.sidecar（元数据齐全）", () => {
    expect(SLOTS["window.sidecar"]).toBeTruthy();
    expect(SLOTS["window.sidecar"].title).toBe("窗口侧栏卡片");
    expect(SLOTS["window.sidecar"].mount).toBe("窗口侧栏");
    expect(SLOT_NAMES).toContain("window.sidecar");
    expect(isSlotName("window.sidecar")).toBe(true);
    expect(isSlotName("not.a.slot")).toBe(false);
  });

  it("J4 · 无 sidecar 贡献时零渲染（不占位、无 aside 节点）", () => {
    registerDemo("demo", []);
    const { container } = render(<SidecarSlot moduleId="calendar" />);
    expect(container.querySelector(".win__sidecar")).toBeNull();
  });

  it("J5 · attachTo=calendar 的贡献只在 calendar 窗渲染，其他窗不渲染", () => {
    registerDemo("demo", ["window.sidecar"]);
    registerContributions("demo", [
      {
        slot: "window.sidecar",
        pluginId: "demo",
        component: () => <div>日程侧栏摘要</div>,
        attachTo: "calendar",
      },
    ]);

    const cal = render(<SidecarSlot moduleId="calendar" />);
    expect(cal.container.querySelector(".win__sidecar")).not.toBeNull();
    expect(screen.getByText("日程侧栏摘要")).toBeTruthy();
    cleanup();

    const other = render(<SidecarSlot moduleId="todo" />);
    expect(other.container.querySelector(".win__sidecar")).toBeNull();
  });

  it("J6 · attachTo 缺省的贡献在所有窗口渲染", () => {
    registerDemo("global", ["window.sidecar"]);
    registerContributions("global", [
      {
        slot: "window.sidecar",
        pluginId: "global",
        component: () => <div>全窗侧栏</div>,
      },
    ]);

    render(<SidecarSlot moduleId="calendar" />);
    expect(screen.getByText("全窗侧栏")).toBeTruthy();
    cleanup();

    render(<SidecarSlot moduleId="agents" />);
    expect(screen.getByText("全窗侧栏")).toBeTruthy();
  });

  it("J5+J6 · attachTo 过滤与缺省全窗并存时互不干扰", () => {
    registerDemo("demo", ["window.sidecar"]);
    registerContributions("demo", [
      {
        slot: "window.sidecar",
        pluginId: "demo",
        component: () => <div>只挂日程</div>,
        attachTo: "calendar",
      },
      {
        slot: "window.sidecar",
        pluginId: "demo",
        component: () => <div>全局侧栏</div>,
      },
    ]);

    render(<SidecarSlot moduleId="calendar" />);
    expect(screen.getByText("只挂日程")).toBeTruthy();
    expect(screen.getByText("全局侧栏")).toBeTruthy();
    cleanup();

    render(<SidecarSlot moduleId="todo" />);
    expect(screen.queryByText("只挂日程")).toBeNull();
    expect(screen.getByText("全局侧栏")).toBeTruthy();
  });

  it("J7 侧证 · 贡献声明 window.sidecar 但 manifest 未声明时被忽略（越权不挂载）", () => {
    registerDemo("rogue", ["dashboard.card"]); // manifest 不含 window.sidecar
    registerContributions("rogue", [
      {
        slot: "window.sidecar",
        pluginId: "rogue",
        component: () => <div>越权侧栏</div>,
        attachTo: "calendar",
      },
    ]);
    const { container } = render(<SidecarSlot moduleId="calendar" />);
    expect(container.querySelector(".win__sidecar")).toBeNull();
  });
});
