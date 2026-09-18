import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { notesApi, type NoteBrief } from "./api";

/**
 * 笔记窗口：搜索索引 + 点开看全文（全文经本机桥按需拉取）。
 * 桥离线时详情 content 为空，列表仍可用。
 */
export default function NotesApp() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState<NoteBrief | null>(null);

  const search = useQuery({
    queryKey: ["notes", "search", q],
    queryFn: () => notesApi.search(q || undefined),
  });

  const detail = useQuery({
    queryKey: ["notes", "detail", selected?.id],
    queryFn: () => notesApi.get(selected!.id),
    enabled: !!selected,
  });

  const syncMut = useMutation({
    mutationFn: async () => {
      const libs = await notesApi.libs();
      const enabled = libs.filter((l) => l.enabled);
      return Promise.all(enabled.map((l) => notesApi.syncLib(l.id)));
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notes"] });
    },
  });

  return (
    <div className="notes-root">
      <div className="notes-toolbar">
        <input
          className="notes-search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="搜索标题或摘要…"
          aria-label="搜索笔记"
        />
        <button
          className="btn"
          type="button"
          disabled={syncMut.isPending}
          onClick={() => syncMut.mutate()}
        >
          {syncMut.isPending ? "同步中…" : "同步"}
        </button>
      </div>
      <div className="notes-body">
        <ul className="notes-list" aria-label="笔记列表">
          {search.isLoading && <li className="empty">加载中…</li>}
          {search.data?.items.length === 0 && (
            <li className="empty">还没有索引，点右上角「同步」从本机桥拉取</li>
          )}
          {search.data?.items.map((n) => (
            <li key={n.id}>
              <button
                type="button"
                className={selected?.id === n.id ? "notes-item notes-item--active" : "notes-item"}
                onClick={() => setSelected(n)}
              >
                <span className="notes-item__title">{n.title || n.rel_path}</span>
                {n.excerpt && <span className="notes-item__excerpt">{n.excerpt}</span>}
              </button>
            </li>
          ))}
        </ul>
        <div className="notes-detail" aria-label="笔记详情">
          {!selected && <div className="empty">选一篇看看</div>}
          {selected && detail.isLoading && <div className="empty">加载中…</div>}
          {selected && detail.data && (
            <>
              <h3 className="notes-detail__title">{detail.data.title}</h3>
              <div className="notes-detail__path">{detail.data.rel_path}</div>
              <pre className="notes-detail__content">
                {detail.data.content || "（全文暂不可用——本机桥未连接）"}
              </pre>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
