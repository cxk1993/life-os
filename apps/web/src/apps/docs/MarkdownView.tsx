/**
 * MarkdownView —— md 渲染组件（T15 导出，供 T16/T17 复用）。
 *
 * ★ 硬要求：md 库必须**懒加载**（动态 import()）—— 只在用户切到「渲染」模式时才加载，
 *   首屏 chunk 里不许出现 md 库。react-markdown 声明式、默认不 dangerouslySetInnerHTML，天然防 XSS。
 *
 * ★ BUG 修复（Qoder CN 2026-09-19 真机验收发现 BUG-T15-1）：
 *   旧实现把 remark-gfm 用 React.lazy 包成「组件对象」塞进 remarkPlugins，
 *   unified 收到的是 React 组件而非插件函数 → 渲染模式必崩（P0）。
 *   修法：remark-gfm 改为「渲染模式触发时动态 import 拿真实函数」，存 state 传给 remarkPlugins。
 *   react-markdown 本身仍用 React.lazy（它是 React 组件，lazy 正确）。
 *
 * 用法：
 *   <MarkdownView content="# 标题" />
 *   <MarkdownView content={...} defaultMode="source" />  // 默认源码模式
 */
import { lazy, Suspense, useEffect, useMemo, useState } from "react";

// ★ 懒加载：只有切到渲染模式才拉 react-markdown（独立 chunk）
const ReactMarkdown = lazy(() => import("react-markdown"));

export type MarkdownMode = "source" | "render";

export interface MarkdownViewProps {
  content: string;
  defaultMode?: MarkdownMode;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type GfmPlugin = any;

/**
 * md 渲染组件：源码 ↔ 渲染 切换。
 * - 源码模式：<pre><code> 显示原文（10 万字也不卡）。
 * - 渲染模式：懒加载 react-markdown（组件）+ remark-gfm（函数，动态 import）。
 */
export function MarkdownView({ content, defaultMode = "render" }: MarkdownViewProps) {
  const [mode, setMode] = useState<MarkdownMode>(defaultMode);
  const [gfm, setGfm] = useState<GfmPlugin | null>(null);
  const [gfmError, setGfmError] = useState<string | null>(null);

  // ★ 只有切到「渲染」模式才加载 remark-gfm（真实函数，不是组件）
  useEffect(() => {
    let cancelled = false;
    if (mode === "render" && !gfm && !gfmError) {
      import("remark-gfm")
        .then((mod) => {
          if (cancelled) return;
          const fn = (mod as unknown as { default?: GfmPlugin }).default ?? mod;
          // ★ BUG-T15-2（Qoder CN 真机复验锁定）：React 的 setter 收到函数会当 updater 调用
          //   fn(prevState) —— remark-gfm 的插件宏在"存入 state"这步就被执行而炸。
          //   必须包一层箭头函数：React 调用它取返回值 fn 存入 state。
          if (typeof fn === "function") {
            setGfm(() => fn);
          } else {
            setGfm(null);
          }
        })
        .catch((err: unknown) => {
          if (cancelled) return;
          setGfmError(err instanceof Error ? err.message : String(err));
        });
    }
    return () => {
      cancelled = true;
    };
  }, [mode, gfm, gfmError]);

  const remarkPlugins = useMemo(() => (gfm ? [gfm] : []), [gfm]);

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
    if (gfmError) {
      return (
        <div className="docs-md-error">
          <p>渲染器加载失败：{gfmError}</p>
          <p>可切回「源码」模式继续查看。</p>
        </div>
      );
    }
    return (
      <Suspense fallback={<div className="docs-md-loading">加载渲染器…</div>}>
        <div className="docs-md-render">
          <ReactMarkdown remarkPlugins={remarkPlugins}>{content}</ReactMarkdown>
        </div>
      </Suspense>
    );
  }, [mode, content, remarkPlugins, gfmError]);

  return (
    <div className="docs-md">
      {toolbar}
      {body}
    </div>
  );
}

export default MarkdownView;
