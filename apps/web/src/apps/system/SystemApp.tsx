/**
 * 系统窗 · V6 系统编排件（主人⑫：能力目录/MCP/推送/账户与鉴权 合并一窗多页）。
 *
 * 形态：真实模块（manifest entry=@/apps/system）→ Dock 自动出「系统」按钮，
 * 零 Dock.tsx 改动（模块注册表驱动，一切皆插件口径）。
 * 页视图源=现有模块 App 复用（React.lazy 保分包）；auth 无前端 app，
 * 用 WindowFrame V5 同款「后端模块 · 仅服务」薄壳语义（win__placeholder 类）。
 */
import { lazy, Suspense } from "react";
import MultitabFrame from "@/kernel/MultitabFrame";

const CatalogApp = lazy(() => import("../catalog/CatalogApp"));
const McpApp = lazy(() => import("../mcp/McpConsoleApp"));
const PushApp = lazy(() => import("../push/PushApp"));

function PageFallback() {
  return <div className="win__placeholder-text" data-testid="system-page-loading">加载中…</div>;
}

/** auth 薄壳页：与 WindowFrame V5 ModulePlaceholder backend 变体同语义（类名同源 win__placeholder）。 */
function AuthBackendPage() {
  return (
    <div className="win__placeholder" role="status" data-testid="system-auth-page">
      <div className="win__placeholder-icon" aria-hidden="true">⚙</div>
      <div className="win__placeholder-title">后端模块 · 仅服务</div>
      <div className="win__placeholder-text">账户与鉴权只提供 API 服务，无独立窗口界面。</div>
      <div className="win__placeholder-meta">module: auth</div>
    </div>
  );
}

export default function SystemApp() {
  return (
    <MultitabFrame
      ariaLabel="系统页签"
      pages={[
        { key: "catalog", label: "能力目录", content: <Suspense fallback={<PageFallback />}><CatalogApp /></Suspense> },
        { key: "mcp", label: "MCP Server", content: <Suspense fallback={<PageFallback />}><McpApp /></Suspense> },
        { key: "push", label: "推送", content: <Suspense fallback={<PageFallback />}><PushApp /></Suspense> },
        { key: "auth", label: "账户与鉴权", content: <AuthBackendPage /> },
      ]}
    />
  );
}
