/**
 * T22 · 窗口能力的 **DOM 层**验证（真渲染 jsdom，不是"读代码觉得对"）。
 *
 * 覆盖验收清单里靠 store 单测覆盖不到的部分：
 *   #1 置顶窗渲染出的 zIndex 落在置顶层（盖过任何普通窗）
 *   #3 固定几何时**缩放手柄整个不在 DOM 里**（不是渲染了再拦）
 *   #6 标题栏出现置顶/固定几何两个按钮（位于最小化/最大化/关闭**左侧**），且状态与 store 同步
 *
 * 说明：窗口内容（React.lazy 加载的插件）在这里会落进错误边界占位，不影响本卡要验的"窗框"。
 */
import { describe, it, expect, beforeEach } from "vitest";
import { render, fireEvent } from "@testing-library/react";

import { WindowFrame } from "./WindowFrame";
import {
  DEFAULT_WORKSPACE_ID,
  PIN_BASE,
  makeWorkspace,
  useDesktopStore,
  type WindowState,
} from "./store";
import type { ModuleManifest } from "./types";

const MANIFEST: ModuleManifest = {
  id: "m1",
  name: "测试窗",
  version: "0.1.0",
  kind: "builtin",
  entry: "@/apps/__t22_none__",
  window: { w: 800, h: 600, minW: 360, minH: 240 },
};

function seed(over: Partial<WindowState> = {}): WindowState {
  const w: WindowState = {
    instanceId: "m1#1",
    moduleId: "m1",
    z: 11,
    minimized: false,
    maximized: false,
    geo: { x: 0, y: 48, w: 800, h: 600 },
    pinned: false,
    fixedGeometry: false,
    workspaceId: DEFAULT_WORKSPACE_ID,
    ...over,
  };
  useDesktopStore.setState({
    modules: { m1: { manifest: MANIFEST, enabled: true } },
    windows: [w],
    workspaces: [makeWorkspace(1, { topZ: 11, seq: 1 })],
    activeWorkspaceId: DEFAULT_WORKSPACE_ID,
  });
  return w;
}

const frame = () => document.querySelector(".win") as HTMLElement | null;
const grips = () => document.querySelectorAll(".win__rz").length;

beforeEach(() => {
  localStorage.clear();
  seed();
});

describe("WindowFrame · T22 窗框行为", () => {
  it("普通窗：zIndex 就是它的 z，缩放手柄齐全，标题栏共 5 个按钮", () => {
    render(<WindowFrame instanceId="m1#1" />);
    expect(frame()?.style.zIndex).toBe("11");
    expect(grips()).toBe(8); // 八个方向
    // 置顶 / 固定几何 / 最小化 / 最大化 / 关闭
    expect(document.querySelectorAll(".win__bar .win__btn").length).toBe(5);
  });

  it("★ 验收#1：置顶窗渲染出的 zIndex 落在置顶层（PIN_BASE 之上）", () => {
    seed({ pinned: true, pinZ: 3 });
    render(<WindowFrame instanceId="m1#1" />);
    expect(frame()?.style.zIndex).toBe(String(PIN_BASE + 3));
    // 与一个高 z 的普通窗相比仍然更靠前
    expect(Number(frame()?.style.zIndex)).toBeGreaterThan(9999);
  });

  it("★ 两个新按钮在最小化/最大化/关闭的**左侧**（DOM 顺序）", () => {
    render(<WindowFrame instanceId="m1#1" />);
    const labels = Array.from(document.querySelectorAll(".win__bar .win__btn")).map((b) =>
      b.getAttribute("aria-label"),
    );
    // 前两个必须是 T22 的新按钮，后三个是原有的
    expect(labels.slice(0, 2)).toEqual(["置顶", "固定位置与大小"]);
    expect(labels.slice(2)).toEqual(["最小化", "最大化", "关闭"]);
  });

  it("★ 验收#3：固定几何时缩放手柄**整个不在 DOM 里**（不是渲染了再拦）", () => {
    seed({ fixedGeometry: true });
    render(<WindowFrame instanceId="m1#1" />);
    expect(grips()).toBe(0);
    // 关掉后手柄回来
    useDesktopStore.getState().setFixedGeometry("m1#1", false);
    expect(useDesktopStore.getState().windows[0].fixedGeometry).toBe(false);
  });

  it("★ 验收#6：点标题栏「置顶」按钮 → store 里真的置顶（状态单向可写）", () => {
    render(<WindowFrame instanceId="m1#1" />);
    const pin = document.querySelector(".win__btn--pin") as HTMLButtonElement;
    expect(pin.getAttribute("aria-pressed")).toBe("false");
    fireEvent.click(pin);
    expect(useDesktopStore.getState().windows[0].pinned).toBe(true);
    expect(useDesktopStore.getState().windows[0].pinZ).toBe(1);
  });

  it("★ 验收#6：置顶 / 固定几何的按钮态与 store 双向一致（is-on）", () => {
    seed({ pinned: true, pinZ: 1, fixedGeometry: true });
    render(<WindowFrame instanceId="m1#1" />);
    expect((document.querySelector(".win__btn--pin") as HTMLElement).className).toContain("is-on");
    expect((document.querySelector(".win__btn--fix") as HTMLElement).className).toContain("is-on");
    // 无障碍态同步
    expect(document.querySelector(".win__btn--pin")?.getAttribute("aria-pressed")).toBe("true");
    expect(document.querySelector(".win__btn--fix")?.getAttribute("aria-pressed")).toBe("true");
  });

  it("固定几何时挂上 win--fixed 类（标题栏不再是可拖拽的暗示）", () => {
    seed({ fixedGeometry: true });
    render(<WindowFrame instanceId="m1#1" />);
    expect(frame()?.className).toContain("win--fixed");
  });

  it("置顶时挂 win--pinned 类（强调色描边的钩子）", () => {
    seed({ pinned: true, pinZ: 1 });
    render(<WindowFrame instanceId="m1#1" />);
    expect(frame()?.className).toContain("win--pinned");
  });
});
