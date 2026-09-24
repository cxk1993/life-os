import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ApiError } from "@/shared/api/client";
import { exportApi, type PreviewOut } from "./api";
import "./export.css";

function errText(e: unknown): string {
  if (e instanceof ApiError) return e.detail || e.title;
  return e instanceof Error ? e.message : "导出预览失败";
}

/** TX-EXPORT-01 · 搬家包中心（V1 只读预览，zip 落盘候派）。 */
export default function ExportApp() {
  const [profile, setProfile] = useState<string | null>(null);
  const [preview, setPreview] = useState<PreviewOut | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const { data: profiles, isLoading } = useQuery({
    queryKey: ["export", "profiles"],
    queryFn: () => exportApi.profiles(),
  });

  const run = async (id: string) => {
    setProfile(id);
    setBusy(true);
    setErr(null);
    setPreview(null);
    try {
      setPreview(await exportApi.preview(id));
    } catch (e) {
      setErr(errText(e));
    } finally {
      setBusy(false);
    }
  };

  const items = profiles?.items ?? [];

  return (
    <div className="export-root">
      <div className="export-hint tiny">
        密钥一律截断（***REDACTED***）· V1 只预览清单与 checksum，zip 落盘候派
      </div>
      <div className="export-list">
        {isLoading ? (
          <div className="empty__text">加载中…</div>
        ) : (
          items.map((p) => (
            <button
              key={p.id}
              type="button"
              className={"export-item" + (profile === p.id ? " export-item--on" : "")}
              onClick={() => run(p.id)}
              disabled={busy}
            >
              {p.title}
              <span className="tiny">{p.id}</span>
            </button>
          ))
        )}
      </div>
      <div className="export-out">
        {err ? (
          <div role="alert" className="export-err">
            {err}
          </div>
        ) : busy ? (
          <div className="empty__text">生成预览…</div>
        ) : !preview ? (
          <div className="empty__text">选一个 profile 看搬家包预览</div>
        ) : (
          <pre className="export-json">{JSON.stringify(preview, null, 2)}</pre>
        )}
      </div>
    </div>
  );
}
