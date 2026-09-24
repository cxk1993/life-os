/**
 * V7 · 统一 Markdown 渲染视图（渲染栈升级：react-markdown + remark-gfm + remark-math + rehype-katex）。
 *
 * ★ 验收样例：主人 Boyle 定律表格（GFM 表格 + $V \propto \dfrac{1}{p}$ LaTeX 公式）。
 * - GFM 表格/删除线/任务列表：remark-gfm
 * - 行内 $...$ / 块级 $$...$$：remark-math → rehype-katex（KaTeX 同步渲染，无回流）
 * - 图片：Obsidian 附件路径由外层按桥契约映射（本组件透传 src，不做二次解析）
 * - 安全：默认不启用 raw HTML（ReactMarkdown skipHtml），防注入
 */
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";

interface Props {
  content: string;
  className?: string;
}

export default function MdView({ content, className }: Props) {
  return (
    <div className={`md-view${className ? ` ${className}` : ""}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        skipHtml
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
