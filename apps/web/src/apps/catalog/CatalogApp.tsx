import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  catalogApi,
  type CatalogEntry,
  type CatalogMcpTool,
  type PluginPermissions,
  type PluginInfoLite,
} from "./api";
import "./catalog.css";

// ★ 来源分组（固定顺序：插件 → 网页 → 内核 → 手动）
const SOURCE_ORDER: { key: string; label: string }[] = [
  { key: "plugin", label: "插件能力" },
  { key: "web_entry", label: "网页入口" },
  { key: "kernel", label: "内核基础" },
  { key: "manual", label: "手动导入" },
];

const KIND_LABEL: Record<string, string> = {
  web: "网页",
  "web+rest": "REST API",
  "web+mcp": "MCP",
};

export default function CatalogApp() {
  const qc = useQueryClient();
  const [query, setQuery] = useState("");
  const [adding, setAdding] = useState(false);

  const { data, isLoading, error } = useQuery({
    queryKey: ["catalog", "entries"],
    queryFn: () => catalogApi.getCatalog(),
    staleTime: 10_000,
  });

  // ★ mcp-console 轻 UI：T18 MCP 工具（AI 可调用能力）展示承接
  const mcpQuery = useQuery({
    queryKey: ["catalog", "mcp-tools"],
    queryFn: () => catalogApi.mcpTools(),
    retry: 1,
  });

  // ★ E2 权限徽标：只读复用 /api/v1/plugins 的 granted permissions（零后端改动）
  const pluginsQuery = useQuery({
    queryKey: ["catalog", "plugins-perms"],
    queryFn: () => catalogApi.plugins(),
    staleTime: 10_000,
    retry: 1,
  });

  // catalog 插件条目 id 为 `plugin.<pid>`，插件清单 id 为 `<pid>`，去前缀建映射
  const permMap = useMemo(() => {
    const m = new Map<string, PluginPermissions>();
    for (const p of (pluginsQuery.data?.plugins ?? []) as PluginInfoLite[]) {
      if (p.id && p.permissions !== undefined && p.permissions !== null) {
        m.set(p.id, p.permissions);
      }
    }
    return m;
  }, [pluginsQuery.data]);

  const toggleMut = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      catalogApi.updateManual(id, { enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["catalog"] }),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => catalogApi.deleteManual(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["catalog"] }),
  });

  // 搜索过滤（名称 / id / capabilities / 端点）
  const filtered = useMemo(() => {
    if (!data?.entries) return [];
    const q = query.trim().toLowerCase();
    if (!q) return data.entries;
    return data.entries.filter((e) =>
      [e.name, e.id, e.endpoint, e.note, ...(e.capabilities || [])]
        .filter(Boolean)
        .some((s) => String(s).toLowerCase().includes(q)),
    );
  }, [data, query]);

  // 按来源分组
  const groups = useMemo(() => {
    const bySource = new Map<string, CatalogEntry[]>();
    for (const e of filtered) {
      const list = bySource.get(e.source) ?? [];
      list.push(e);
      bySource.set(e.source, list);
    }
    return SOURCE_ORDER.map(({ key, label }) => ({
      key,
      label,
      items: bySource.get(key) ?? [],
    })).filter((g) => g.items.length > 0);
  }, [filtered]);

  if (isLoading)
    return (
      <div className="catalog-root">
        <div className="catalog-hint">加载中…</div>
      </div>
    );
  if (error) {
    return (
      <div className="catalog-root">
        <div className="catalog-hint">
          目录加载失败：{(error as Error).message}
          <button onClick={() => qc.invalidateQueries({ queryKey: ["catalog"] })}>重试</button>
        </div>
      </div>
    );
  }

  const counts = data?.counts ?? {};

  return (
    <div className="catalog-root">
      {/* 头部：标题 + 搜索 + 新建 */}
      <div className="catalog-head">
        <div className="catalog-title">能力目录</div>
        <input
          className="catalog-search"
          placeholder="搜索能力 / 名称 / 端点…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button className="catalog-add-btn" onClick={() => setAdding(!adding)}>
          {adding ? "收起" : "+ 手动导入"}
        </button>
      </div>

      {/* 汇总行 */}
      <div className="catalog-counts">
        {Object.entries(counts).map(([k, v]) => (
          <span key={k} className="catalog-count">
            {k}: {v}
          </span>
        ))}
      </div>

      {adding && <ManualForm onDone={() => setAdding(false)} />}

      {groups.length === 0 && <div className="catalog-hint">没有匹配的能力条目</div>}

      {/* 分组列表 */}
      {groups.map((g) => (
        <section key={g.key} className="catalog-group">
          <div className="catalog-group-title">
            {g.label} <span className="catalog-group-count">{g.items.length}</span>
          </div>
          <div className="catalog-items">
            {g.items.map((e) => (
              <div key={e.id} className={`catalog-item ${e.enabled ? "" : "is-disabled"}`}>
                <div className="catalog-item-main">
                  <div className="catalog-item-name">
                    {e.name}
                    <span className="catalog-item-kind">{KIND_LABEL[e.kind] ?? e.kind}</span>
                  </div>
                  <div className="catalog-item-meta">
                    <code>{e.id}</code>
                    {e.endpoint && <code>{e.endpoint}</code>}
                    {e.auth_ref && e.auth_ref !== "none" && (
                      <span className="catalog-auth">{e.auth_ref}</span>
                    )}
                  </div>
                  {e.capabilities.length > 0 && (
                    <div className="catalog-caps">
                      {e.capabilities.map((c) => (
                        <span key={c} className="catalog-cap">
                          {c}
                        </span>
                      ))}
                    </div>
                  )}
                  <PluginPermissionRow entry={e} permMap={permMap} />
                  {e.note && <div className="catalog-note">{e.note}</div>}
                </div>
                <div className="catalog-item-actions">
                  {e.source === "manual" ? (
                    <>
                      <button
                        className="catalog-toggle"
                        title={e.enabled ? "点击停用" : "点击启用"}
                        onClick={() => toggleMut.mutate({ id: e.id, enabled: !e.enabled })}
                      >
                        {e.enabled ? "开" : "关"}
                      </button>
                      <button
                        className="catalog-del"
                        title="删除"
                        onClick={() => deleteMut.mutate(e.id)}
                      >
                        ×
                      </button>
                    </>
                  ) : (
                    <span className={`catalog-dot ${e.enabled ? "on" : "off"}`} />
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>
      ))}

      {/* ★ mcp-console 轻 UI：AI 工具（MCP）区块 —— T18 27 工具展示承接 */}
      <McpToolsSection
        tools={mcpQuery.data ?? null}
        isLoading={mcpQuery.isLoading}
        error={mcpQuery.error}
      />
    </div>
  );
}

// ─────────── ★ E2 权限徽标（令19 三裁 / 令21 路B：granted 数据源，纯前端） ───────────

interface NormBadge {
  key: string;
  label: string;
  cls: string;
}

interface NormPerms {
  core: NormBadge[]; // 核心 5 枚常显（风险语义）
  detail: NormBadge[]; // 细节 4 枚进 hover（资源级 token）
  raw: string; // 原始 permissions 文本
  kind: "array" | "object";
}

// 回环主机：net:out:<host> 命中这些算「本机网络」，其余（含 *）算外网
const LOOPBACK_HOSTS = new Set(["localhost", "127.0.0.1", "::1"]);
// provides/capabilities 里出现这些动词即视为「有写能力」，不发只读徽标
const WRITE_VERB = /(write|create|update|delete|remove|manage|admin|exec|send|set|import|sync)/i;
const READ_VERB =
  /(read|get|list|query|view|health|today|stats|summary|overview|compass|growth|trend|check)/i;

/**
 * 把 granted permissions（旧数组 token / 新粗布尔对象）归一为两层徽标。
 * 规则与令19 三裁、E2 v2 静态原型逐一对齐：
 *  - 网络四选一：🔒无网络 / 🌐本机 / 🌍外网（数组可精确到主机）；对象 network=true 仅显中性「🌐 可联网」
 *  - 📖只读：无 db:own/fs/子进程 且 provides 仅读无写
 *  - ⚙️子进程：subprocess（对象）或对应数组 token
 *  - 细节层：🗄️db:own / 🌉bridge:read / 📁fs:plugin / 🔔notify:send（收进 hover，附原始 JSON）
 */
function normalizePermissions(perms: PluginPermissions, capabilities: string[]): NormPerms {
  const isObject = !Array.isArray(perms) && typeof perms === "object" && perms !== null;

  let net: "none" | "local" | "external" | "unknown" = "none";
  let subprocess = false;
  let hasDb = false;
  let hasFs = false;
  let hasBridge = false;
  let hasNotify = false;

  if (Array.isArray(perms)) {
    for (const raw of perms) {
      const t = String(raw);
      if (t === "db:own") hasDb = true;
      else if (t === "bridge:read") hasBridge = true;
      else if (t === "fs:plugin" || t.startsWith("fs:")) hasFs = true;
      else if (t === "notify:send" || t.startsWith("notify:")) hasNotify = true;
      else if (
        t === "subprocess" ||
        t.startsWith("subprocess:") ||
        t === "proc:exec" ||
        t.startsWith("proc:")
      )
        subprocess = true;
      else if (t.startsWith("net:out")) {
        const host = t.slice("net:out:".length).trim();
        if (host === "" || host === "*") net = "external";
        else if (LOOPBACK_HOSTS.has(host.toLowerCase())) {
          if (net !== "external") net = "local";
        } else net = "external";
      }
    }
  } else if (isObject) {
    const o = perms as Record<string, boolean>;
    if (o.network === true) net = "unknown"; // 粗布尔：不区分本机/外网，显中性
    if (o.subprocess === true) subprocess = true;
    if (o.filesystem === true) hasFs = true;
  }

  const detail: NormBadge[] = [];
  if (hasDb) detail.push({ key: "db", label: "🗄️ db:own", cls: "catalog-pbadge--info" });
  if (hasBridge)
    detail.push({ key: "bridge", label: "🌉 bridge:read", cls: "catalog-pbadge--violet" });
  if (hasFs) detail.push({ key: "fs", label: "📁 fs:plugin", cls: "catalog-pbadge--warn" });
  if (hasNotify)
    detail.push({ key: "notify", label: "🔔 notify:send", cls: "catalog-pbadge--violet" });

  const core: NormBadge[] = [];
  if (net === "external")
    core.push({ key: "net-ext", label: "🌍 外部网络", cls: "catalog-pbadge--danger" });
  else if (net === "local")
    core.push({ key: "net-local", label: "🌐 本机网络", cls: "catalog-pbadge--warn" });
  else if (net === "unknown")
    core.push({ key: "net-any", label: "🌐 可联网", cls: "catalog-pbadge--warn" });
  else core.push({ key: "net-none", label: "🔒 无网络", cls: "catalog-pbadge--safe" });

  const caps = capabilities ?? [];
  const readOnly =
    !hasDb &&
    !hasFs &&
    !subprocess &&
    caps.length > 0 &&
    caps.every((c) => !WRITE_VERB.test(c)) &&
    caps.some((c) => READ_VERB.test(c));
  if (readOnly) core.push({ key: "readonly", label: "📖 只读", cls: "catalog-pbadge--safe" });
  if (subprocess)
    core.push({ key: "subprocess", label: "⚙️ 子进程", cls: "catalog-pbadge--danger" });

  return {
    core,
    detail,
    raw: JSON.stringify(perms ?? []),
    kind: isObject ? "object" : "array",
  };
}

function PluginPermissionRow({
  entry,
  permMap,
}: {
  entry: CatalogEntry;
  permMap: Map<string, PluginPermissions>;
}) {
  // 仅 plugin 源显示权限；插件清单尚未就绪或查无此 pid 时不渲染（避免假「无网络」）
  if (entry.source !== "plugin") return null;
  const pid = entry.id.replace(/^plugin\./, "");
  const perms = permMap.get(pid);
  if (perms === undefined) return null;

  const norm = normalizePermissions(perms, entry.capabilities);
  const detailTitle =
    norm.kind === "object"
      ? "声明式权限（filesystem/network/subprocess 布尔）"
      : norm.detail.length > 0
        ? "资源级权限（旧数组 token）"
        : "无资源级 token（自身不建表/不触文件桥通知）";

  return (
    <div className="catalog-perms">
      {norm.core.map((b) => (
        <span key={b.key} className={`catalog-pbadge ${b.cls}`}>
          {b.label}
        </span>
      ))}
      <span className="catalog-perms-detail" tabIndex={0} role="button" aria-label="权限明细">
        🔑 权限明细 {norm.detail.length}
        <span className="catalog-perms-pop" role="tooltip">
          <span className="catalog-perms-pop-title">{detailTitle}</span>
          {norm.detail.length > 0 && (
            <span className="catalog-perms-pop-badges">
              {norm.detail.map((b) => (
                <span key={b.key} className={`catalog-pbadge ${b.cls}`}>
                  {b.label}
                </span>
              ))}
            </span>
          )}
          <code className="catalog-perms-pop-raw">{norm.raw}</code>
        </span>
      </span>
    </div>
  );
}

const MCP_METHOD_BADGE: Record<string, string> = {
  GET: "catalog-mcp-badge--get",
  POST: "catalog-mcp-badge--post",
  PUT: "catalog-mcp-badge--put",
  DELETE: "catalog-mcp-badge--delete",
};

function McpToolsSection({
  tools,
  isLoading,
  error,
}: {
  tools: CatalogMcpTool[] | null;
  isLoading: boolean;
  error: Error | null;
}) {
  // 按插件分组
  const byPlugin = useMemo(() => {
    const map = new Map<string, CatalogMcpTool[]>();
    for (const t of tools ?? []) {
      const list = map.get(t.plugin_id) ?? [];
      list.push(t);
      map.set(t.plugin_id, list);
    }
    return [...map.entries()];
  }, [tools]);

  return (
    <section className="catalog-group catalog-mcp-section">
      <div className="catalog-group-title">
        AI 工具（MCP） <span className="catalog-group-count">{tools?.length ?? 0}</span>
      </div>
      {isLoading && <div className="catalog-hint">工具加载中…</div>}
      {!isLoading && error && (
        <div className="catalog-hint">工具列表加载失败（后端未启用 mcp？）</div>
      )}
      {!isLoading && !error && (tools?.length ?? 0) === 0 && (
        <div className="catalog-hint">
          当前没有插件声明 provides —— 在插件的 manifest 加一行 provides，这里就会自动多出一个 AI
          工具。
        </div>
      )}
      {!isLoading &&
        !error &&
        byPlugin.map(([pluginId, list]) => (
          <div key={pluginId} className="catalog-mcp-plugin">
            <div className="catalog-mcp-plugin-title">{pluginId}</div>
            <table className="catalog-mcp-table">
              <thead>
                <tr>
                  <th>工具名</th>
                  <th>调用</th>
                  <th>scope</th>
                  <th>说明</th>
                </tr>
              </thead>
              <tbody>
                {list.map((t) => (
                  <tr key={t.name}>
                    <td className="catalog-mcp-mono">{t.name}</td>
                    <td>
                      <span className={`catalog-mcp-badge ${MCP_METHOD_BADGE[t.method] ?? ""}`}>
                        {t.method}
                      </span>{" "}
                      <span className="catalog-mcp-mono catalog-mcp-path">{t.path}</span>
                    </td>
                    <td className="catalog-mcp-mono">{t.scope}</td>
                    <td className="catalog-mcp-desc">{t.description}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
    </section>
  );
}

// ───────────────────────── 手动导入表单 ─────────────────────────

function ManualForm({ onDone }: { onDone: () => void }) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [kind, setKind] = useState("web");
  const [url, setUrl] = useState("");
  const [endpoint, setEndpoint] = useState("");
  const [authRef, setAuthRef] = useState("");
  const [caps, setCaps] = useState("");
  const [note, setNote] = useState("");
  const [err, setErr] = useState("");

  const createMut = useMutation({
    mutationFn: () =>
      catalogApi.createManual({
        name,
        kind,
        url: url.trim() || null,
        endpoint: endpoint.trim() || null,
        auth_ref: authRef.trim() || null,
        capabilities: caps.split(/[,，\s]+/).filter(Boolean),
        note: note.trim() || null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["catalog"] });
      onDone();
    },
    onError: (e) => setErr((e as Error).message),
  });

  return (
    <form
      className="catalog-form"
      onSubmit={(ev) => {
        ev.preventDefault();
        if (!name.trim()) {
          setErr("名称必填");
          return;
        }
        setErr("");
        createMut.mutate();
      }}
    >
      <div className="catalog-form-row">
        <input placeholder="名称 *" value={name} onChange={(e) => setName(e.target.value)} />
        <select value={kind} onChange={(e) => setKind(e.target.value)}>
          <option value="web">网页</option>
          <option value="web+rest">REST API</option>
          <option value="web+mcp">MCP</option>
        </select>
      </div>
      <div className="catalog-form-row">
        <input
          placeholder="url（http/https）"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
        />
      </div>
      <div className="catalog-form-row">
        <input
          placeholder="endpoint（REST/MCP 必填）"
          value={endpoint}
          onChange={(e) => setEndpoint(e.target.value)}
        />
        <input
          placeholder="auth_ref（如 pat:env:TOKEN）"
          value={authRef}
          onChange={(e) => setAuthRef(e.target.value)}
        />
      </div>
      <div className="catalog-form-row">
        <input
          placeholder="capabilities，逗号分隔"
          value={caps}
          onChange={(e) => setCaps(e.target.value)}
        />
      </div>
      <div className="catalog-form-row">
        <input placeholder="备注（可选）" value={note} onChange={(e) => setNote(e.target.value)} />
        <button type="submit" disabled={createMut.isPending}>
          {createMut.isPending ? "保存中…" : "保存"}
        </button>
      </div>
      {err && <div className="catalog-form-err">{err}</div>}
    </form>
  );
}
