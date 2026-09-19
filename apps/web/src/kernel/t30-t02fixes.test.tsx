/**
 * T30 · ★ 顺修 T02 两疑点的回归测试（ACCEPT-T02 实测过的两个问题，锁死防回归）。
 *
 *   疑点① Esc 不关窗语义 —— 根因：`useHotkey` 没有"正在输入"守卫，
 *          在任何输入框里按 Esc 会把用户正在打字的窗口关掉。
 *          修法：裸键 + 焦点在可编辑元素 → 跳过（`shared/hooks/useHotkey.ts`）。
 *   疑点② 窄屏新窗宽度未钳制 —— 根因：`defaultGeo` 直接用 manifest 的 w/h。
 *          修法：新窗初始尺寸钳进视口（`kernel/store.ts`）。
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { makeWorkspace, useDesktopStore } from "./store";
import { useHotkey } from "@/shared/hooks/useHotkey";
import type { ModuleManifest } from "./types";

// ───────────────────────── 疑点① ─────────────────────────
function EscProbe({ onEsc }: { onEsc: () => void }): React.JSX.Element {
  useHotkey("escape", onEsc);
  return <input data-testid="inp" defaultValue="" />;
}

describe("★ T02 疑点①：Esc 在输入框里不再关窗", () => {
  it("焦点在输入框里按 Esc → **不**触发全局关窗", () => {
    const onEsc = vi.fn();
    render(<EscProbe onEsc={onEsc} />);
    const inp = screen.getByTestId("inp");
    inp.focus();
    fireEvent.keyDown(inp, { key: "Escape" });
    expect(onEsc).not.toHaveBeenCalled(); // ★ 修复点：以前这里会被调用
  });

  it("桌面空白处按 Esc → 仍然关窗（原语义保留）", () => {
    const onEsc = vi.fn();
    render(<EscProbe onEsc={onEsc} />);
    fireEvent.keyDown(document.body, { key: "Escape" });
    expect(onEsc).toHaveBeenCalledTimes(1);
  });

  it("★ 带修饰键的组合不受输入守卫影响（Ctrl+K 仍全局可用）", () => {
    let fired = 0;
    function KProbe(): React.JSX.Element {
      useHotkey("mod+k", () => {
        fired += 1;
      });
      return <input data-testid="inp2" defaultValue="" />;
    }
    render(<KProbe />);
    const inp = screen.getByTestId("inp2");
    inp.focus();
    fireEvent.keyDown(inp, { key: "k", ctrlKey: true });
    expect(fired).toBe(1); // ★ mod 组合在输入框里也生效（搜索入口就是这么用的）
  });
});

// ───────────────────────── 疑点② ─────────────────────────
const BIG: ModuleManifest = {
  id: "big",
  name: "大窗",
  version: "0",
  kind: "builtin",
  entry: "@/apps/__none__",
  window: { w: 5000, h: 3000, minW: 360, minH: 240 },
};

describe("★ T02 疑点②：窄屏上开大窗 → 尺寸被钳进视口", () => {
  it("新窗宽不超过视口宽、高不超过视口可用高", () => {
    useDesktopStore.setState({
      modules: { big: { manifest: BIG, enabled: true } },
      windows: [],
      workspaces: [makeWorkspace(1)],
      activeWorkspaceId: "ws1",
    });
    useDesktopStore.getState().openWindow("big");

    const geo = useDesktopStore.getState().windows[0].geo;
    expect(geo.w).toBeLessThanOrEqual(window.innerWidth); // ★ 以前是 5000 > 视口
    expect(geo.h).toBeLessThanOrEqual(window.innerHeight);
    // ★ 不低于 minW/minH（钳制不能把窗压到不可用）
    expect(geo.w).toBeGreaterThanOrEqual(BIG.window.minW ?? 0);
    expect(geo.h).toBeGreaterThanOrEqual(BIG.window.minH ?? 0);
  });
});
