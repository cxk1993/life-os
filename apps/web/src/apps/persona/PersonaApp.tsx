/**
 * 人格体系主界面（T16）：文件管理器壳，复用 T15 导出组件。
 *
 * - 左：DocsTree（从 @apps/docs 导入），固定「人格体系」专属根节点
 *   （首次进入自动用 docs.node.write 建一个 kind=folder, name="人格体系" 的根）
 * - 右：DocsViewer（txt/md 查看与编辑，md 渲染懒加载）
 * - 底部：搜索（调 T15 /search，结果限定人格根子树）
 *
 * ★ 不重写树组件 / 查看器 / md 渲染器；按钮逻辑/接口/表结构不出现人格概念。
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { usePluginEvent } from "@/shared/api/events";
import { docsApi, type DocsNode } from "../docs/api";
import { DocsTree } from "../docs/DocsTree";
import { DocsViewer } from "../docs/DocsViewer";
import "./persona.css";

const PERSONA_ROOT_NAME = "人格体系";
/** ★ BUG-T16-1 修复：固定 slug 标记正根（创建前查重 + 启动对账用）。 */
const PERSONA_ROOT_SLUG = "root:persona";

/** 判断节点是否带正根标记（旧数据可能没有 → 视为候选根）。 */
function isPersonaRoot(n: DocsNode): boolean {
  return n.kind === "folder" && n.name === PERSONA_ROOT_NAME;
}

export default function PersonaApp() {
  const qc = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [searchQ, setSearchQ] = useState("");
  const [rootId, setRootId] = useState<string | null>(null);

  // ① 加载森林，找「人格体系」根（首次进入自动创建）
  const { data: tree = [], isFetched } = useQuery({
    queryKey: ["docs", "tree"],
    queryFn: () => docsApi.tree(),
  });

  // ② 确保人格根存在：先按 slug 查重（幂等），没有才创建
  const ensureRoot = useMutation({
    mutationFn: () =>
      docsApi.create({
        kind: "folder",
        name: PERSONA_ROOT_NAME,
        meta_json: { slug: PERSONA_ROOT_SLUG },
      }),
    onSuccess: (node) => {
      setRootId(node.id);
      qc.invalidateQueries({ queryKey: ["docs"] });
    },
  });

  // ★ BUG-T16-1 修复：挂载幂等 —— 只在「查询完成且确实无根」时创建一次
  useEffect(() => {
    if (!isFetched) return; // 查询未完成不动作（关键：避免 loading 期重复创建）
    const roots = tree.filter(isPersonaRoot);
    if (roots.length > 0) {
      // 优先选带 slug 标记的正根；都没有则选最早创建的（保留现场）
      const canonical =
        roots.find(
          (n) => n.meta_json && (n.meta_json as Record<string, unknown>).slug === PERSONA_ROOT_SLUG,
        ) ?? roots[0];
      setRootId(canonical.id);
      // ★ 启动对账（兜底）：其余同名根软删归档（历史脏数据自动收敛）
      const dupes = roots.filter((n) => n.id !== canonical.id);
      if (dupes.length > 0) {
        for (const d of dupes) {
          docsApi.remove(d.id).catch(() => {
            /* 对账失败不阻塞 UI；下次挂载再试 */
          });
        }
      }
      return;
    }
    if (!ensureRoot.isPending && !ensureRoot.isSuccess) {
      ensureRoot.mutate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tree, isFetched]);

  // ③ 只取人格根子树（前端按 rootId 过滤，避免拉全部文档）
  const personaNodes = useMemo(() => {
    if (!rootId) return [];
    // tree 是森林；找到人格根节点
    const root = tree.find((n) => n.id === rootId);
    return root ? [root] : [];
  }, [tree, rootId]);

  const { data: detail } = useQuery({
    queryKey: ["docs", "detail", selectedId],
    queryFn: () => (selectedId ? docsApi.get(selectedId) : Promise.resolve(null)),
    enabled: !!selectedId,
  });

  const { data: searchResults } = useQuery({
    queryKey: ["docs", "search", searchQ],
    queryFn: () => docsApi.search(searchQ),
    enabled: searchQ.trim().length > 0,
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["docs"] });

  usePluginEvent("docs.node.created", invalidate);
  usePluginEvent("docs.node.updated", invalidate);
  usePluginEvent("docs.node.deleted", invalidate);
  usePluginEvent("docs.node.restored", invalidate);

  const createMut = useMutation({
    mutationFn: (body: { parent_id?: string | null; kind: "folder" | "doc"; name: string }) =>
      docsApi.create(body),
    onSuccess: (node) => {
      invalidate();
      setSelectedId(node.id);
    },
  });

  const renameMut = useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) => docsApi.update(id, { name }),
    onSuccess: invalidate,
  });

  const moveMut = useMutation({
    mutationFn: ({ id, parentId }: { id: string; parentId: string | null }) =>
      docsApi.update(id, { parent_id: parentId }),
    onSuccess: invalidate,
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => docsApi.remove(id),
    onSuccess: () => {
      invalidate();
      setSelectedId(null);
    },
  });

  const saveMut = useMutation({
    mutationFn: ({ id, format, body }: { id: string; format: string; body: string }) =>
      docsApi.saveContent(id, { format, body }),
    onSuccess: invalidate,
  });

  const handleSelect = (node: DocsNode) => {
    setSelectedId(node.id);
    setSearchQ("");
  };

  // 搜索结果限定人格根子树
  const filteredHits = useMemo(() => {
    if (!rootId || !searchResults) return [];
    const root = tree.find((n) => n.id === rootId);
    if (!root) return [];
    const subIds = new Set<string>();
    const walk = (list: DocsNode[]) => {
      for (const n of list) {
        subIds.add(n.id);
        walk(n.children ?? []);
      }
    };
    walk([root]);
    return searchResults.items.filter((n: DocsNode) => subIds.has(n.id));
  }, [searchResults, rootId, tree]);

  return (
    <div className="persona-root">
      <div className="persona-header">
        <span className="persona-title">🧠 人格体系</span>
        <input
          className="persona-search"
          placeholder="在人格体系内搜索…"
          value={searchQ}
          onChange={(e) => setSearchQ(e.target.value)}
        />
      </div>

      <div className="persona-layout">
        <div className="persona-pane persona-pane-tree">
          <DocsTree
            nodes={personaNodes}
            selectedId={selectedId}
            onSelect={handleSelect}
            onCreate={(parentId, kind, name) =>
              createMut.mutate({ parent_id: parentId ?? rootId, kind, name })
            }
            onRename={(id, name) => renameMut.mutate({ id, name })}
            onMove={(id, parentId) => moveMut.mutate({ id, parentId })}
            onDelete={(id) => deleteMut.mutate(id)}
          />
        </div>

        <div className="persona-pane persona-pane-viewer">
          {searchQ.trim() ? (
            <div className="persona-search-results">
              <div className="persona-search-title">搜索：{searchQ}</div>
              {filteredHits.map((n: DocsNode) => (
                <button
                  key={n.id}
                  type="button"
                  className="persona-hit"
                  onClick={() => handleSelect(n)}
                >
                  {n.name}
                </button>
              ))}
              {filteredHits.length === 0 && <div className="persona-empty">人格体系内没有命中</div>}
            </div>
          ) : detail ? (
            <DocsViewer
              name={detail.name}
              format={detail.format ?? "md"}
              body={detail.body ?? ""}
              onSave={(format, body) => saveMut.mutate({ id: detail.id, format, body })}
            />
          ) : (
            <div className="persona-empty">← 在左侧新建或选择一个文稿</div>
          )}
        </div>
      </div>
    </div>
  );
}

export { PersonaApp };
