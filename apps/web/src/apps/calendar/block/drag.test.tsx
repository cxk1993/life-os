import { describe, it, expect, vi } from "vitest";
import { render, act } from "@testing-library/react";
import { useBlockDrag } from "./useBlockDrag";
import { useBlockResize } from "./useBlockResize";
import { useCreateDrag } from "./useCreateDrag";

/** jsdom 不实现 PointerEvent，用带 clientX/Y/button 的 MouseEvent 模拟。 */
function firePointer(node: Element, type: string, props: Record<string, unknown>) {
  node.dispatchEvent(new MouseEvent(type, { bubbles: true, ...props }));
}
function fireWindow(type: string, props: Record<string, unknown>) {
  window.dispatchEvent(new MouseEvent(type, { ...props }));
}

describe("useBlockDrag", () => {
  it("纵向吸附 15min、横向吸附 1 天（T27 卡要求）", () => {
    const onCommit = vi.fn();
    function H() {
      const { start } = useBlockDrag({ hourHeight: 60, dayWidth: 100, onCommit });
      return (
        <div data-testid="b" onPointerDown={start} style={{ width: 50, height: 30 }}>
          b
        </div>
      );
    }
    const { getByTestId } = render(<H />);
    const el = getByTestId("b");
    act(() => firePointer(el, "pointerdown", { clientX: 10, clientY: 10, button: 0 }));
    act(() => fireWindow("pointermove", { clientX: 110, clientY: 100 }));
    act(() => fireWindow("pointerup", { clientX: 110, clientY: 100 }));
    // dy=90px / 60px/h = 1.5h = 90min，本来就是 15min 倍数 → 吸附后仍是 1.5
    expect(onCommit).toHaveBeenCalledWith({ dDays: 1, dHours: 1.5 });
  });

  it("亚格子位移仍吸附到最近 15min", () => {
    const onCommit = vi.fn();
    function H() {
      const { start } = useBlockDrag({ hourHeight: 60, dayWidth: 100, onCommit });
      return <div data-testid="b" onPointerDown={start} />;
    }
    const { getByTestId } = render(<H />);
    const el = getByTestId("b");
    act(() => firePointer(el, "pointerdown", { clientX: 0, clientY: 0, button: 0 }));
    act(() => fireWindow("pointermove", { clientX: 0, clientY: 73 })); // ~1.216h → 1.216/0.25=4.87→round5→1.25h
    act(() => fireWindow("pointerup", { clientX: 0, clientY: 73 }));
    const d = onCommit.mock.calls[0][0] as { dHours: number };
    expect(d.dHours).toBe(1.25);
  });
});

describe("useBlockResize", () => {
  it("下缘拉伸：吸附 15min 粒度（90px=1.5h 仍成立）", () => {
    const onCommit = vi.fn();
    function H() {
      const { start } = useBlockResize({ hourHeight: 60, dayWidth: 100, onCommit });
      return <div data-testid="b" onPointerDown={(e) => start("bottom")(e)} />;
    }
    const { getByTestId } = render(<H />);
    const el = getByTestId("b");
    act(() => firePointer(el, "pointerdown", { clientX: 0, clientY: 0, button: 0 }));
    act(() => fireWindow("pointermove", { clientX: 0, clientY: 90 }));
    act(() => fireWindow("pointerup", { clientX: 0, clientY: 90 }));
    expect(onCommit).toHaveBeenCalledWith("bottom", { dHours: 1.5, dDays: 0 });
  });
  it("右缘拉伸：吸附整天数", () => {
    const onCommit = vi.fn();
    function H() {
      const { start } = useBlockResize({ hourHeight: 60, dayWidth: 100, onCommit });
      return <div data-testid="b" onPointerDown={(e) => start("right")(e)} />;
    }
    const { getByTestId } = render(<H />);
    const el = getByTestId("b");
    act(() => firePointer(el, "pointerdown", { clientX: 0, clientY: 0, button: 0 }));
    act(() => fireWindow("pointermove", { clientX: 200, clientY: 0 }));
    act(() => fireWindow("pointerup", { clientX: 200, clientY: 0 }));
    expect(onCommit).toHaveBeenCalledWith("right", { dHours: 0, dDays: 2 });
  });
});

describe("useCreateDrag", () => {
  it("空白处拖拽换算成本地时间（吸附 15min）", () => {
    const onCommit = vi.fn();
    const rect = {
      left: 0,
      top: 0,
      width: 700,
      height: 1104,
    } as unknown as DOMRect;
    const getGridRect = () => rect;
    function H() {
      const { start } = useCreateDrag({
        hourHeight: 46,
        dayWidth: 100,
        weekStart: new Date(2026, 8, 14),
        getGridRect,
        onCommit,
      });
      return <div data-testid="g" onPointerDown={start} style={{ width: 700, height: 1104 }} />;
    }
    const { getByTestId } = render(<H />);
    const el = getByTestId("g");
    // day1 (150/100=1) → 2026-09-15，y=92 → 2h；拖动到 y=138 → 3h
    act(() => firePointer(el, "pointerdown", { clientX: 150, clientY: 92, button: 0 }));
    act(() => fireWindow("pointermove", { clientX: 150, clientY: 138 }));
    act(() => fireWindow("pointerup", { clientX: 150, clientY: 138 }));
    expect(onCommit).toHaveBeenCalledTimes(1);
    const [s, e] = onCommit.mock.calls[0] as [string, string];
    expect(new Date(s).getDate()).toBe(15);
    expect(new Date(s).getHours()).toBe(2);
    expect(new Date(e).getHours()).toBe(3);
  });
});
