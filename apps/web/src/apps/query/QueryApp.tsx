import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ApiError } from "@/shared/api/client";
import { queryApi, type QueryResult } from "./api";
import { loadPrefs, savePrefs } from "./prefs";
import "./query.css";

function errText(e: unknown): string {
  if (e instanceof ApiError) return e.detail || e.title;
  return e instanceof Error ? e.message : "查询失败";
}

/** TX-QUERY-01 · 跨模块预置查询（只读）。 */
export default function QueryApp() {
  const [qid, setQid] = useState<string | null>(null);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const { data: presets, isLoading } = useQuery({
    queryKey: ["query", "presets"],
    queryFn: () => queryApi.presets(),
  });

  const run = async (id: string) => {
    setQid(id);
    setBusy(true);
    setErr(null);
    setResult(null);
    try {
      setResult(await queryApi.run(id));
    } catch (e) {
      setErr(errText(e));
    } finally {
      setBusy(false);
    }
  };

  const items = presets?.items ?? [];
  const rows = result?.rows ?? [];

  return (
    <div className="query-root">
      <div className="query-list">
        {isLoading ? (
          <div className="empty__text">加载中…</div>
        ) : items.length === 0 ? (
          <div className="empty__text">暂无预置查询</div>
        ) : (
          items.map((p) => (
            <button
              key={p.id}
              type="button"
              className={"query-item" + (qid === p.id ? " query-item--on" : "")}
              onClick={() => run(p.id)}
              disabled={busy}
            >
              {p.title}
            </button>
          ))
        )}
      </div>
      <div className="query-out">
        {err ? (
          <div role="alert" className="query-err">
            {err}
          </div>
        ) : busy ? (
          <div className="empty__text">查询中…</div>
        ) : !result ? (
          <div className="empty__text">点左侧一条预置查询</div>
        ) : result.empty ? (
          <div className="empty__text">{result.query?.empty_text || "没有结果"}</div>
        ) : (
          <>
            <div className="tiny" style={{ color: "var(--txt-faint)" }}>
              {result.query?.id || qid} · {result.row_count} 条
              {result.partial ? " · 部分源不可用" : ""}
            </div>
            <ul className="query-rows">
              {rows.map((r, i) => (
                <li key={i} className="query-row">
                  {Object.entries(r)
                    .filter(([k]) => k !== "id")
                    .map(([k, v]) => (
                      <span key={k} className="query-cell">
                        <em>{k}</em> {String(v ?? "")}
                      </span>
                    ))}
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </div>
  );
}
