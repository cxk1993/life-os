/**
 * ★ 知识库 · 三合一窗口（主人 ⑤：「复盘 / 笔记 / 文档 可以合并成一个入口端，
 *   并且也在同一个窗口内展示，你可以分成窗口内多个页面的分页形式」）
 *
 * 实现（astrbot 下场 · 2026-09-25 · 接替下线的知默）：
 *   复用 `kernel/MultitabFrame`，三页 = 复盘 / 笔记 / 文档。
 *   页视图源**直接复用现有模块 App**（懒加载，不重写业务）。
 *
 * ★ 本轮范围（第一刀）：**三合一入口 + 一窗多页**。
 * ★ 未做（留后续，如实标注）：OB 树深同步 / 附件映射 / MathJax / 笔记可写自动保存 /
 *   复盘增删笔记 —— 属后端与桥层，非本刀范围。
 */
import { lazy, Suspense } from "react";
import MultitabFrame from "@/kernel/MultitabFrame";

const ReviewApp = lazy(() => import("../review/ReviewApp"));
const NotesApp = lazy(() => import("../notes/NotesApp"));
const DocsApp = lazy(() => import("../docs/DocsApp"));

function PageFallback() {
  return <div className="dash-muted" data-testid="knowledge-loading">加载中…</div>;
}

const wrap = (node: React.ReactNode) => (
  <Suspense fallback={<PageFallback />}>{node}</Suspense>
);

export default function KnowledgeApp() {
  return (
    <div className="knowledge-win" style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <MultitabFrame
        ariaLabel="知识库"
        persistKey="knowledge-win"
        pages={[
          { key: "review", label: "复盘", content: wrap(<ReviewApp />) },
          { key: "notes", label: "笔记", content: wrap(<NotesApp />) },
          { key: "docs", label: "文档", content: wrap(<DocsApp />) },
        ]}
      />
    </div>
  );
}
