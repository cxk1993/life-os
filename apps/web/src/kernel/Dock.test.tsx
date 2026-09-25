/**
 * ★ DOCK_MERGE 防回潮判据（workbuddy 2026-09-25 收尾 · 依总监令 9 §2）。
 *
 * 背景：令 9 §2 确立「**Dock 显隐的唯一杠杆是 `DOCK_MERGE`，不是 `manifest.slots`**」——
 *   MiMo 曾用「摘 `desktop.dock` 槽」想隐藏按钮，**无效**，因为 Dock 是
 *   `Object.values(modules).map(...)`（遍历 store 全部模块），**从不读 slots**。
 *
 * 本文件锁三件事（防同类返工再犯）：
 *  ① **机制事实**：**没有** `desktop.dock` 槽的模块**仍会出现**在 Dock（所以"摘槽"永远无效）；
 *  ② **归口生效**：`DOCK_MERGE` 里的模块**不单独出按钮**（容器模块存在时）；
 *  ③ **fail-safe**：容器模块**不存在** → **保留原按钮**（绝不因合并丢入口）。
 */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Dock } from "./Dock";
import { useDesktopStore } from "./store";
import type { ModuleManifest } from "./types";

interface MiniMod {
  id: string;
  name?: string;
  slots?: string[];
}

function setModules(list: MiniMod[]): void {
  const modules: Record<string, { manifest: ModuleManifest; enabled: boolean }> = {};
  for (const m of list) {
    modules[m.id] = {
      manifest: {
        id: m.id,
        name: m.name ?? m.id,
        version: "0.1.0",
        kind: "builtin",
        ...(m.slots ? { slots: m.slots } : {}),
      } as unknown as ModuleManifest,
      enabled: true,
    };
  }
  useDesktopStore.setState({ modules, windows: [] });
}

afterEach(() => {
  cleanup();
  useDesktopStore.setState({ modules: {}, windows: [] });
});

describe("Dock · DOCK_MERGE 归口机制（令 9 §2 判据）", () => {
  it("① 机制事实：**没有** desktop.dock 槽的模块仍会出现（所以'摘槽隐藏'永远无效）", () => {
    setModules([{ id: "somemod", name: "某模块" }]); // ← 故意不给 slots
    render(<Dock />);
    expect(screen.getByLabelText("某模块")).toBeTruthy();
  });

  it("② 归口生效：DOCK_MERGE 命中的模块不单独出按钮（容器在时）", () => {
    setModules([
      { id: "system", name: "系统" },
      { id: "query", name: "跨模块查询" }, // ← DOCK_MERGE: query → system
      { id: "plugins", name: "插件管理" }, // ← DOCK_MERGE: plugins → system
      { id: "export", name: "导出中心" }, // ← DOCK_MERGE: export → system
    ]);
    render(<Dock />);
    // 容器在
    expect(screen.getByLabelText(/^系统/)).toBeTruthy();
    // 被归口者**不出现**（getByLabelText 会抛，故用 queryBy）
    expect(screen.queryByLabelText("跨模块查询")).toBeNull();
    expect(screen.queryByLabelText("插件管理")).toBeNull();
    expect(screen.queryByLabelText("导出中心")).toBeNull();
    // 角标显示并入数量（system 吸收了 query/plugins/export 等）
    expect(screen.getByText(/^\+\d+$/)).toBeTruthy();
  });

  it("③ fail-safe：容器不存在时**保留原按钮**（绝不因合并丢入口）", () => {
    setModules([{ id: "query", name: "跨模块查询" }]); // ← 无 system 容器
    render(<Dock />);
    expect(screen.getByLabelText("跨模块查询")).toBeTruthy();
  });

  it("④ 覆盖面：DOCK_MERGE 关键成员一处齐（新增归口请同步此表，防漏收）", () => {
    // 与 Dock.tsx 的 DOCK_MERGE 保持同源期望：主人点名的并入面
    const expected = [
      "catalog",
      "mcp",
      "push",
      "auth",
      "export",
      "query",
      "plugins",
      "review",
      "notes",
      "docs",
      "diary",
      "persona",
      "health",
    ];
    setModules([
      { id: "system", name: "系统" },
      { id: "knowledge", name: "知识库" },
      { id: "growth", name: "成长罗盘" },
      ...expected.map((id) => ({ id, name: id })),
    ]);
    render(<Dock />);
    const buttons = screen.getAllByRole("button");
    // 只剩三个容器（其余全部被归口）
    expect(buttons).toHaveLength(3);
    expect(screen.getByLabelText(/^系统/)).toBeTruthy();
    expect(screen.getByLabelText(/^知识库/)).toBeTruthy();
    expect(screen.getByLabelText(/^成长罗盘/)).toBeTruthy();
  });
});
