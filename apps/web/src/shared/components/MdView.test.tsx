/**
 * V7 渲染栈判据 · MdView 组件级（astrbot 补 · 「V7 判据对照样例」）
 *
 * 为什么单独一份：NotesApp.test.tsx 的 Boyle 样例是**端到端**验收（走 NotesApp），
 * 本文件是**组件级**判据，覆盖主人 ⑤ 点名但端到端未覆盖的三处：
 *   ① 块级公式 $$...$$（端到端只验了行内 $...$）
 *   ② 图片附件透传（主人原话：「ob 笔记的附件、图片插入的这个 md 文件展示功能也要加上」）
 *   ③ 安全：raw HTML 不得执行（MdView 声明 skipHtml）
 * 另附「已知缺口」判据（wiki 链接 [[...]]）——**skip 标注，作为待办锚点**。
 */
import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import MdView from "./MdView";

describe("V7 · MdView 渲染栈判据", () => {
  it("GFM 表格：渲染为 <table>（4 列表头）", () => {
    const md = "| A | B | C | D |\n|---|---|---|---|\n| 1 | 2 | 3 | 4 |";
    const { container } = render(<MdView content={md} />);
    expect(container.querySelector("table")).toBeTruthy();
    expect(container.querySelectorAll("table th").length).toBe(4);
  });

  it("行内公式 $...$：渲染为 KaTeX 节点", () => {
    const { container } = render(<MdView content={"体积 $V \\propto \\dfrac{1}{p}$ 成立"} />);
    expect(container.querySelector(".katex")).toBeTruthy();
  });

  it("★ 块级公式 $$...$$：渲染为 KaTeX display 节点", () => {
    const { container } = render(<MdView content={"$$\nV \\propto \\dfrac{1}{p}\n$$"} />);
    expect(container.querySelector(".katex")).toBeTruthy();
    // 块级应带 display 模式标记
    expect(container.querySelector(".katex-display")).toBeTruthy();
  });

  it("★ 图片：src 原样透传（附件路径由外层桥映射）", () => {
    const { container } = render(<MdView content={"![图](attachments/a.png)"} />);
    const img = container.querySelector("img");
    expect(img).toBeTruthy();
    expect(img?.getAttribute("src")).toBe("attachments/a.png");
  });

  it("★ 安全：raw HTML 不渲染（skipHtml，防注入）", () => {
    const { container } = render(
      <MdView content={'<script>window.__pwned=1</script>\n\n<b>bold?</b>'} />
    );
    expect(container.querySelector("script")).toBeNull();
    // skipHtml：HTML 标签本身不应被解析为元素（按文本处理或丢弃）
    expect(container.querySelector("b")).toBeNull();
  });

  it("GFM 删除线/任务列表：渲染为对应结构", () => {
    const { container } = render(<MdView content={"- [x] 完成\n- [ ] 未完成\n\n~~删~~"} />);
    expect(container.querySelectorAll('input[type="checkbox"]').length).toBe(2);
    expect(container.querySelector("del")).toBeTruthy();
  });

  // ── 已知缺口（★ 待办锚点，不阻塞）─────────────────────────────────────
  it.skip("★ 缺口：Obsidian wiki 链接 [[note]] 应可跳转（当前无 remark-wiki-link 依赖）", () => {
    // 现状：package.json 无 wiki-link 插件 → [[note]] 会按纯文本渲染
    // 主人 ⑤ 点名「像 obsidian 一样」→ 建议随 V7 深同步一并补
    const { container } = render(<MdView content={"参见 [[Boyle 定律]]"} />);
    expect(container.querySelector("a.wiki-link")).toBeTruthy();
  });
});
