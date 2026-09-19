/**
 * MarkdownView —— md 渲染组件（T15 导出，供 T16/T17 复用）。
 *
 * ★ 硬要求：md 库必须**懒加载**（动态 import()）—— 只在用户切到「渲染」模式时才加载，
 *   首屏 chunk 里不许出现 md 库。react-markdown 声明式、默认不 dangerouslySetInnerHTML，天然防 XSS。
 *
 * 用法：
 *   <MarkdownView content="# 标题" />
 *   <MarkdownView content={...} defaultMode="source" />  // 默认源码模式
 */
import { lazy, Suspense, useMemo, useState } from "react";

// ★ 懒加载：只有切到渲染模式才拉 react-markdown + remark-gfm（各自独立 chunk）
const ReactMarkdown = lazy(() => import("react-markdown"));
// remark-gfm 是 ESM 模块（default 可能是模块自身或 {default}），统一转成函数
const RemarkGfm = lazy(async () => {
  const mod = await import("remark-gfm");
  const fn = (mod as unknown as { default?: unknown }).default ?? mod;
  return { default: fn as never };
});

export type MarkdownMode = "source" | "render";

export interface MarkdownViewProps {
  content: string;
  defaultMode?: MarkdownMode;
}

/**
 * md 渲染组件：源码 ↔ 渲染 切换。
 * - 源码模式：<pre><code> 显示原文（10 万字也不卡）。
 * - 渲染模式：懒加载 react-markdown + remark-gfm（GFM 表格/删除线/任务列表）。
 */
export function MarkdownView({ content, defaultMode = "render" }: MarkdownViewProps) {
  const [mode, setMode] = useState<MarkdownMode>(defaultMode);

  const toolbar = (
    <div className="docs-md-toolbar">
      <button
        type="button"
        className={`docs-md-btn ${mode === "source" ? "active" : ""}`}
        onClick={() => setMode("source")}
      >
        源码
      </button>
      <button
        type="button"
        className={`docs-md-btn ${mode === "render" ? "active" : ""}`}
        onClick={() => setMode("render")}
      >
        渲染
      </button>
    </div>
  );

  const body = useMemo(() => {
    if (mode === "source" || content.length === 0) {
      return (
        <pre className="docs-md-source">
          <code>{content || "（空）"}</code>
        </pre>
      );
    }
    return (
      <Suspense fallback={<div className="docs-md-loading">加载渲染器…</div>}>
        <div className="docs-md-render">
          <ReactMarkdown remarkPlugins={[RemarkGfm as never]}>{content}</ReactMarkdown>
        </div>
      </Suspense>
    );
  }, [mode, content]);

  return (
    <div className="docs-md">
      {toolbar}
      {body}
    </div>
  );
}

export default MarkdownView;
