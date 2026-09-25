/**
 * ★ ⑨ 理财 · 分页内嵌（主人原话：「理财这个插件/模块窗口只是以分页的形式去内嵌外部网页」）
 *
 * 实现（astrbot 下场 · 2026-09-25 · 主人令「你也下场，全力以赴」）：
 *   用 `kernel/MultitabFrame` 把窗口分为两页：
 *     ①「账本」= **同源反代** `/ext/beecount/login` 的 iframe（⑨ 的"内嵌外部网页"形态）
 *     ②「本地流水」= **原 FinanceApp 原样搬入**（零删减，业务逻辑不动）
 *
 * 安全（照本席 W 判据）：
 *   - F-2 **同源**：iframe src 用 `/ext/beecount/login`，**绝不出现上游绝对域**（同源反代已配）；
 *   - F-3 W-1：`/ext/` 白名单在 nginx 层守（非白名单 404，已实测）；
 *   - F-4 W-2：仅 https/同源相对路径；
 *   - F-5 W-3：sandbox 含 allow-scripts/allow-forms/allow-popups，
 *     ★ **不含** allow-top-navigation（防劫持整站）；
 *   - F-6 登录态：同源反代 → cookie 为 first-party（真机验）。
 *
 * 回退：若本组件异常，把 `index.tsx` 的 Component 改回 `FinanceApp` 即可（原文件未动）。
 */
import MultitabFrame from "@/kernel/MultitabFrame";
import FinanceApp from "./FinanceApp";

/** ★ 同源反代路径（绝不写上游绝对域 —— F-2 纪律）。 */
const BEECOUNT_EMBED_PATH = "/ext/beecount/login";

function BeecountEmbed() {
  return (
    <iframe
      title="BeeCount 账本"
      src={BEECOUNT_EMBED_PATH}
      className="finance-embed"
      style={{ width: "100%", height: "100%", border: 0, display: "block" }}
      sandbox="allow-scripts allow-forms allow-popups allow-same-origin"
      referrerPolicy="no-referrer"
      loading="lazy"
    />
  );
}

export default function FinanceTabbedApp() {
  return (
    <div className="finance-tabbed" style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <MultitabFrame
        ariaLabel="理财"
        persistKey="finance"
        pages={[
          { key: "beecount", label: "账本（BeeCount）", content: <BeecountEmbed /> },
          { key: "local", label: "本地流水", content: <FinanceApp /> },
        ]}
      />
    </div>
  );
}
