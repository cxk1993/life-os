/**
 * 文档树主界面（T15）：左树 + 右查看器（文件管理器形态）。
 *
 * - 左：DocsTree（树形文件管理器：新建/重命名/移动/删除/回收站）
 * - 右：DocsViewer（txt/md 查看与编辑，md 渲染懒加载）
 * - 底部工具条：回收站 / 搜索
 * - 订阅 SSE 事件（docs.node.*）做增量刷新
 *
 * ★ 这是「通用文档浏览器」入口（T16/T17 只复用组件，不做业务）。
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { usePluginEvent } from "@/shared/api/events";
import { docsApi, type DocsNode } from "./api";
import DocsTree from "./DocsTree";
import DocsViewer from "./DocsViewer";

export default function DocsApp() {
  const qc = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [searchQ, setSearchQ] = useState("");
  const [showTrash, setShowTrash] = useState(false);

  const { data: tree = [] } = useQuery({
    queryKey: ["docs", "tree"],
    queryFn: () => docsApi.tree(),
  });

  const { data: detail } = useQuery({
    queryKey: ["docs", "detail", selectedId],
    queryFn: () => (selectedId ? docsApi.get(selectedId) : Promise.resolve(null)),
    enabled: !!selectedId,
  });

  const { data: trash } = useQuery({
    queryKey: ["docs", "trash"],
    queryFn: () => docsApi.trash(),
    enabled: showTrash,
  });

  const { data: searchResults } = useQuery({
    queryKey: ["docs", "search", searchQ],
    queryFn: () => docsApi.search(searchQ),
    enabled: searchQ.trim().length > 0,
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["docs"] });
  };

  // SSE 事件 → 增量刷新
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

  const restoreMut = useMutation({
    mutationFn: (id: string) => docsApi.restore(id),
    onSuccess: invalidate,
  });

  const purgeMut = useMutation({
    mutationFn: (id: string) => docsApi.purge(id),
    onSuccess: invalidate,
  });

  const saveMut = useMutation({
    mutationFn: ({ id, format, body }: { id: string; format: string; body: string }) =>
      docsApi.saveContent(id, { format, body }),
    onSuccess: invalidate,
  });

  const handleSelect = (node: DocsNode) => {
    setSelectedId(node.id);
    setShowTrash(false);
    setSearchQ("");
  };

  return (
    <div className="docs-root">
      <div className="docs-layout">
        <div className="docs-pane docs-pane-tree">
          <DocsTree
            nodes={tree}
            selectedId={selectedId}
            onSelect={handleSelect}
            onCreate={(parentId, kind, name) =>
              createMut.mutate({ parent_id: parentId, kind, name })
            }
            onRename={(id, name) => renameMut.mutate({ id, name })}
            onMove={(id, parentId) => moveMut.mutate({ id, parentId })}
            onDelete={(id) => deleteMut.mutate(id)}
          />
        </div>

        <div className="docs-pane docs-pane-viewer">
          {showTrash ? (
            <div className="docs-trash">
              <div className="docs-trash-header">
                <span>回收站</span>
                <button type="button" onClick={() => setShowTrash(false)}>
                  返回
                </button>
              </div>
              {(trash?.items ?? []).map((n: DocsNode) => (
                <div key={n.id} className="docs-trash-item">
                  <span>{n.name}</span>
                  <button type="button" onClick={() => restoreMut.mutate(n.id)}>
                    恢复
                  </button>
                  <button
                    type="button"
                    className="danger"
                    onClick={() => {
                      if (window.confirm(`彻底删除「${n.name}」？不可恢复！`))
                        purgeMut.mutate(n.id);
                    }}
                  >
                    彻底删除
                  </button>
                </div>
              ))}
              {(trash?.items ?? []).length === 0 && <div className="docs-empty">回收站是空的</div>}
            </div>
          ) : searchQ.trim() ? (
            <div className="docs-search-results">
              <div className="docs-trash-header">
                <span>搜索：{searchQ}</span>
                <button type="button" onClick={() => setSearchQ("")}>
                  清除
                </button>
              </div>
              {(searchResults?.items ?? []).map((n: DocsNode) => (
                <button
                  key={n.id}
                  type="button"
                  className="docs-search-hit"
                  onClick={() => handleSelect(n)}
                >
                  {n.name}
                </button>
              ))}
              {(searchResults?.items ?? []).length === 0 && (
                <div className="docs-empty">没有命中</div>
              )}
            </div>
          ) : detail ? (
            <DocsViewer
              name={detail.name}
              format={detail.format ?? "md"}
              body={detail.body ?? ""}
              onSave={(format, body) => saveMut.mutate({ id: detail.id, format, body })}
            />
          ) : (
            <div className="docs-empty">← 在左侧选择或新建一个文档</div>
          )}
        </div>
      </div>

      <div className="docs-footer">
        <input
          className="docs-search-input"
          placeholder="搜索文档（中文友好）…"
          value={searchQ}
          onChange={(e) => setSearchQ(e.target.value)}
        />
        <button type="button" onClick={() => setShowTrash((v) => !v)}>
          {showTrash ? "隐藏回收站" : "回收站"}
        </button>
      </div>
    </div>
  );
}

export { DocsApp };
