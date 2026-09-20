/**
 * useDragMove / useResize —— pointercancel 守卫回归测试（评审 2026-09-20）。
 *
 * 背景：拖动/缩放中指针被系统取消（触屏手势接管 / Alt+Tab / 输入法弹窗）时，
 * 此前 window 上的 pointermove/pointerup 监听会泄漏，且 onMove 不分 pointerId，
 * 泄漏期内任何鼠标移动都会让窗口跳变。修复后：pointercancel 即中止全部监听
 * 并还原视觉（拖动还原 transform；缩放还原起始几何），store 不被污染。
 *
 * 测试策略：jsdom 无 PointerEvent 且 React 委托对降级 pointer 事件不触发，
 * 因此探针组件用**原生 addEventListener** 绑 handler，事件用富化属性的
 * Event 实例手工派发（handler 只读 button/pointerId/clientX/clientY/preventDefault）。
 */
import { render, screen } from "@testing-library/react";
import { useEffect, useRef } from "react";
import { describe, expect, it, beforeAll, beforeEach } from "vitest";

import { useDesktopStore } from "./store";
import { useDragMove } from "./useDragMove";
import { useResize } from "./useResize";

function probeWindow() {
  useDesktopStore.setState({
    windows: [
      {
        instanceId: "probe",
        moduleId: "probe-mod",
        z: 10,
        minimized: false,
        maximized: false,
        geo: { x: 100, y: 80, w: 400, h: 300 },
        pinned: false,
        fixedGeometry: false,
        workspaceId: "ws1",
      },
    ],
  });
}

beforeAll(() => {
  HTMLElement.prototype.setPointerCapture = () => {};
  HTMLElement.prototype.releasePointerCapture = () => {};
});

beforeEach(() => {
  probeWindow();
});

/** 造一个带指针属性的富化 Event（handler 只读这些字段）。 */
function pointerEvent(type: string, x: number, y: number): Event {
  const ev = new Event(type, { bubbles: true, cancelable: true });
  Object.assign(ev, {
    button: 0,
    pointerId: 1,
    clientX: x,
    clientY: y,
    preventDefault: () => {},
    stopPropagation: () => {},
  });
  return ev;
}

function DragProbe() {
  const ref = useRef<HTMLDivElement>(null);
  const handler = useDragMove("probe", ref, true);
  useEffect(() => {
    const el = ref.current!;
    const bound = handler as unknown as EventListener;
    el.addEventListener("pointerdown", bound);
    return () => el.removeEventListener("pointerdown", bound);
  }, [handler]);
  return <div ref={ref} data-testid="drag-el" style={{ left: 100, top: 80 }} />;
}

function ResizeProbe() {
  const ref = useRef<HTMLDivElement>(null);
  const manifest = {
    id: "probe-mod",
    name: "probe",
    version: "0",
    kind: "builtin" as const,
    entry: "",
    window: { w: 400, h: 300, minW: 200, minH: 150 },
  };
  const handler = useResize("probe", ref, manifest, true);
  useEffect(() => {
    const el = ref.current!;
    const wrapped = (e: Event) => handler(e as never, "e");
    el.addEventListener("pointerdown", wrapped as EventListener);
    return () => el.removeEventListener("pointerdown", wrapped as EventListener);
  }, [handler]);
  return <div ref={ref} data-testid="resize-el" style={{ left: 100, top: 80, width: 400, height: 300 }} />;
}

describe("useDragMove · pointercancel 守卫", () => {
  it("cancel 后还原 transform，且后续 pointermove 不再生效（监听已移除）", () => {
    render(<DragProbe />);
    const el = screen.getByTestId("drag-el");

    el.dispatchEvent(pointerEvent("pointerdown", 10, 10));
    window.dispatchEvent(pointerEvent("pointermove", 40, 30));
    expect(el.style.transform).toBe("translate(30px, 20px)");

    el.dispatchEvent(pointerEvent("pointercancel", 0, 0));
    expect(el.style.transform).toBe("");

    // 泄漏回归：cancel 之后任何 pointermove 不得再改样式
    window.dispatchEvent(pointerEvent("pointermove", 200, 200));
    expect(el.style.transform).toBe("");
  });

  it("正常路径回归：down → move → up 仍提交吸附几何，且监听清干净", () => {
    render(<DragProbe />);
    const el = screen.getByTestId("drag-el");

    el.dispatchEvent(pointerEvent("pointerdown", 0, 0));
    window.dispatchEvent(pointerEvent("pointermove", 48, 80));
    el.dispatchEvent(pointerEvent("pointerup", 48, 80));

    const geo = useDesktopStore
      .getState()
      .windows.find((w) => w.instanceId === "probe")!.geo;
    expect(geo.x).toBe(48); // base offsetLeft(jsdom=0) + 48，恰在 8px 网格上
    expect(geo.y).toBe(80); // 80 > TOPBAR(48)，不触发顶栏钳制

    // up 之后监听应已移除：再 move 不改 transform
    window.dispatchEvent(pointerEvent("pointermove", 999, 999));
    expect(el.style.transform).toBe("");
  });
});

describe("useResize · pointercancel 守卫", () => {
  it("cancel 后还原起始几何样式，且后续 pointermove 不再生效，store 全程未污染", () => {
    render(<ResizeProbe />);
    const el = screen.getByTestId("resize-el");

    el.dispatchEvent(pointerEvent("pointerdown", 0, 0));
    window.dispatchEvent(pointerEvent("pointermove", 60, 0));
    expect(el.style.width).toBe("460px");

    el.dispatchEvent(pointerEvent("pointercancel", 0, 0));
    expect(el.style.left).toBe("100px");
    expect(el.style.top).toBe("80px");
    expect(el.style.width).toBe("400px");
    expect(el.style.height).toBe("300px");

    // 泄漏回归：cancel 之后任何 pointermove 不得再改样式
    window.dispatchEvent(pointerEvent("pointermove", 500, 500));
    expect(el.style.width).toBe("400px");
    // store 全程未被污染（缩放未提交）
    const geo = useDesktopStore
      .getState()
      .windows.find((w) => w.instanceId === "probe")!.geo;
    expect(geo).toEqual({ x: 100, y: 80, w: 400, h: 300 });
  });

  it("正常路径回归：down → move → up 仍提交新几何", () => {
    render(<ResizeProbe />);
    const el = screen.getByTestId("resize-el");

    el.dispatchEvent(pointerEvent("pointerdown", 0, 0));
    window.dispatchEvent(pointerEvent("pointermove", 64, 0));
    el.dispatchEvent(pointerEvent("pointerup", 64, 0));

    const geo = useDesktopStore
      .getState()
      .windows.find((w) => w.instanceId === "probe")!.geo;
    expect(geo.w).toBe(464);
    expect(geo.x).toBe(104); // snap(100)=104：提交时吸附 8px 网格是既有生产行为
  });
});
