/**
 * MarkdownView 真渲染冒烟测试（★ 不 mock react-markdown / remark-gfm）。
 *
 * 为什么存在：BUG-T15-1（remark-gfm 被包成 React.lazy 组件）与 BUG-T15-2（setGfm(fn)
 * 被 React 当 updater 执行插件函数）都发生在**真实 unified 渲染管线**里，
 * mock 掉 react-markdown 的测试在结构上摸不到它们（Qoder CN 真机复验的教训）。
 * 本文件必须保持「零 mock」：谁往这里加 vi.mock 谁 = 拆掉 P0 防线。
 */
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MarkdownView } from "./MarkdownView";

describe("MarkdownView 真渲染冒烟（不 mock）", () => {
  it("渲染模式输出真实 <h1>（插件以真实函数进入 unified，不触发 updater 误执行）", async () => {
    render(<MarkdownView content="# 一行标题" />);

    await waitFor(
      () => {
        const h1 = screen.getByRole("heading", { level: 1 });
        expect(h1.textContent).toBe("一行标题");
      },
      { timeout: 5000 },
    );
  });

  it("GFM 表格与删除线（remark-gfm 真插件生效）", async () => {
    const md = "| a | b |\n| - | - |\n| 1 | 2 |\n\n~~划掉~~";
    render(<MarkdownView content={md} />);

    await waitFor(
      () => {
        expect(document.querySelector("table")).not.toBeNull();
        expect(document.querySelector("del")).not.toBeNull();
      },
      { timeout: 5000 },
    );
  });

  it("源码模式不加载渲染器（原文直出）", () => {
    render(<MarkdownView content="# 源码模式" defaultMode="source" />);
    expect(screen.getByText("# 源码模式")).toBeTruthy();
    expect(document.querySelector("table")).toBeNull();
  });
});
