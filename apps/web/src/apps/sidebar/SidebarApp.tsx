import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/shared/api/client";

interface Item {
  id: string;
  type: string;
  label: string;
  abbr: string;
  href: string;
  node_ref: string;
  group: string;
  order: number;
  enabled: boolean;
}

function errText(e: unknown): string {
  if (e instanceof ApiError) return e.detail || e.title;
  return e instanceof Error ? e.message : "请求失败";
}

/** TX-SIDEBAR-02 · 侧栏自定义容器（高度自定义）。 */
export default function SidebarApp() {
  const qc = useQueryClient();
  const [label, setLabel] = useState("");
  const [href, setHref] = useState("");
  const [group, setGroup] = useState("");
  const [err, setErr] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["sidebar", "items"],
    queryFn: () => api.get<{ items: Item[]; count: number }>("/api/v1/sidebar/items"),
  });

  const createMut = useMutation({
    mutationFn: () =>
      api.post<Item>("/api/v1/sidebar/items", {
        type: "link",
        label: label.trim(),
        href: href.trim(),
        group: group.trim(),
      }),
    onSuccess: () => {
      setLabel("");
      setHref("");
      setErr(null);
      qc.invalidateQueries({ queryKey: ["sidebar"] });
    },
    onError: (e) => setErr(errText(e)),
  });

  const delMut = useMutation({
    mutationFn: (id: string) => api.delete(`/api/v1/sidebar/items/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sidebar"] }),
    onError: (e) => setErr(errText(e)),
  });

  const items = data?.items ?? [];

  return (
    <div className="sidebar-root">
      <form
        className="sidebar-add"
        onSubmit={(e) => {
          e.preventDefault();
          if (!label.trim() || !href.trim() || createMut.isPending) return;
          createMut.mutate();
        }}
      >
        <input
          placeholder="标题"
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          aria-label="标题"
        />
        <input
          placeholder="https://…"
          value={href}
          onChange={(e) => setHref(e.target.value)}
          aria-label="链接"
        />
        <input
          placeholder="分组"
          value={group}
          onChange={(e) => setGroup(e.target.value)}
          aria-label="分组"
        />
        <button type="submit" className="btn btn--primary" disabled={createMut.isPending}>
          添加
        </button>
      </form>
      {err ? (
        <div role="alert" className="sidebar-err">
          {err}
        </div>
      ) : null}
      <div className="sidebar-list">
        {isLoading ? (
          <div>加载中…</div>
        ) : items.length === 0 ? (
          <div>还没有自定义条目——加一个书签/友链吧</div>
        ) : (
          items.map((it) => (
            <div key={it.id} className="sidebar-row">
              <span className="sidebar-abbr">{it.abbr || it.label.slice(0, 2)}</span>
              <span className="sidebar-label">{it.label}</span>
              <span className="tiny">{it.group}</span>
              <a href={it.href} target="_blank" rel="noreferrer">
                打开
              </a>
              <button
                type="button"
                className="btn"
                aria-label={`删除 ${it.label}`}
                onClick={() => delMut.mutate(it.id)}
              >
                删
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
