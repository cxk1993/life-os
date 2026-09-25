/**
 * 系统窗 · V6 系统编排件（主人⑫：能力目录/MCP/推送/账户与鉴权 合并一窗多页）。
 *
 * 形态：真实模块（manifest entry=@/apps/system）→ Dock 自动出「系统」按钮，
 * 零 Dock.tsx 改动（模块注册表驱动，一切皆插件口径）。
 *
 * ★ tabs 配置面（令 78 指点·候容器型模块 schema）：
 * - 本组件自读 store 注册表里自己模块的 manifest；schema 定稿后 manifest 若带
 *   `tabs: [{ key, label, entry? }]`，按声明渲染（entry 页 lazy 复用该模块 App，
 *   无 entry 页 = 薄壳「后端模块 · 仅服务」语义）；
 * - manifest 无 tabs（现状）→ 用下方默认四页 fallback，行为与已部署版一致。
 */
import { lazy, Suspense } from "react";
import MultitabFrame from "@/kernel/MultitabFrame";
import { useDesktopStore } from "@/kernel/store";

/** schema 定稿后 manifest.tabs 的形状（知默容器型模块草案；本组件只依赖此最小面）。 */
interface DeclaredTab {
  key: string;
  label: string;
  /** 模块 id——指向注册表内另一模块的 App；缺省 = 无 UI 后端模块（薄壳语义页）。 */
  entry?: string;
}

/** 模块 id → 已知 App 组件的 lazy 映射（新页签接入在此登记一行）。 */
const KNOWN_APPS: Record<string, React.LazyExoticComponent<React.ComponentType>> = {
  catalog: lazy(() => import("../catalog/CatalogApp")),
  mcp: lazy(() => import("../mcp/McpConsoleApp")),
  push: lazy(() => import("../push/PushApp")),
  // ★ 主人 2026-09-25：「导出中心」并入系统窗多页（第 5 页）
  export: lazy(() => import("../export/ExportApp")),
  // ★ 主人 2026-09-25：「跨区块查询」「插件管理」并入系统窗多页
  query: lazy(() => import("../query/QueryApp")),
  plugins: lazy(() => import("../plugins/PluginsApp")),
};

const DEFAULT_TABS: DeclaredTab[] = [
  { key: "catalog", label: "能力目录", entry: "catalog" },
  { key: "mcp", label: "MCP Server", entry: "mcp" },
  { key: "push", label: "推送", entry: "push" },
  { key: "export", label: "导出中心", entry: "export" }, // ★ 主人新增
  { key: "query", label: "跨区块查询", entry: "query" }, // ★ 主人新增
  { key: "plugins", label: "插件管理", entry: "plugins" }, // ★ 主人新增
  { key: "auth", label: "账户与鉴权" }, // auth 无前端 app → 薄壳语义页
];

function PageFallback() {
  return <div className="win__placeholder-text" data-testid="system-page-loading">加载中…</div>;
}

/** 薄壳语义页：与 WindowFrame V5 ModulePlaceholder backend 变体同语义（类名同源 win__placeholder）。 */
function BackendOnlyPage({ label }: { label: string }) {
  return (
    <div className="win__placeholder" role="status" data-testid={`system-backend-page-${label}`}>
      <div className="win__placeholder-icon" aria-hidden="true">⚙</div>
      <div className="win__placeholder-title">已接入（后端服务）</div>
      <div className="win__placeholder-text">该模块已接入：提供后端 API 服务，无独立窗口界面。</div>
    </div>
  );
}

export default function SystemApp() {
  // 自读注册表：manifest.tabs（候 schema）→ 配置化；无 → 默认四页。
  const manifest = useDesktopStore((s) => s.modules["system"]?.manifest);
  const declared = (manifest as { tabs?: DeclaredTab[] } | undefined)?.tabs;
  const tabs = declared?.length ? declared : DEFAULT_TABS;

  const pages = tabs.map((tab) => {
    const Known = tab.entry ? KNOWN_APPS[tab.entry] : undefined;
    return {
      key: tab.key,
      label: tab.label,
      content: Known ? (
        <Suspense fallback={<PageFallback />}>
          <Known />
        </Suspense>
      ) : (
        <BackendOnlyPage label={tab.key} />
      ),
    };
  });

  return (
    <MultitabFrame
      ariaLabel="系统页签"
      persistKey="system"
      pages={pages}
    />
  );
}
