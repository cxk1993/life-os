/**
 * 日记主界面（T17）：月历入口 + 当天快速记录 + 收件箱。
 *
 * ★ 复用 T15 导出的 DocsViewer（txt/md、源码↔渲染、md 懒加载），不重写编辑器。
 * ★ 打开第一眼 = 今天 + 收件箱（「记于任何处 + 复盘时归纳」的真实习惯）。
 * ★ 本卡不建表：正文读写全走 T15 docs API；定位走本卡 /api/v1/diary/*。
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { usePluginEvent } from "@/shared/api/events";
import { toast } from "@/shared/components/Toast";
import { ApiError } from "@/shared/api/client";
import { docsApi, type DocsNodeDetail } from "../docs/api";
import { DocsViewer } from "../docs/DocsViewer";
import { diaryApi } from "./api";
import DateNavigator from "./DateNavigator";
import "./diary.css";

function todayLocalStr(): string {
  // 本地时区切天（浏览器本地时间即主人环境 Asia/Shanghai）
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export default function DiaryApp() {
  const qc = useQueryClient();
  const [date, setDate] = useState<string | null>(null); // 当前查看/编辑的日期
  const [tab, setTab] = useState<"entry" | "inbox">("entry");
  const [viewYm, setViewYm] = useState(() => {
    const d = new Date();
    return { year: d.getFullYear(), month: d.getMonth() + 1 };
  });

  // ① 默认定位到「今天」
  useEffect(() => {
    if (date === null) setDate(todayLocalStr());
  }, [date]);

  // ② 月历高亮（已有日记的日期）
  const { data: monthData } = useQuery({
    queryKey: ["diary", "month", viewYm.year, viewYm.month],
    queryFn: () => diaryApi.month(viewYm.year, viewYm.month),
  });

  // ③ 当前日期的节点 id（get-or-create 幂等）
  const { data: entry } = useQuery({
    queryKey: ["diary", "entry", date],
    queryFn: () => (date ? diaryApi.entry(date) : Promise.resolve(null)),
    enabled: !!date,
  });

  // ④ 节点正文
  const { data: detail } = useQuery({
    queryKey: ["docs", "detail", entry?.node_id],
    queryFn: () => (entry ? docsApi.get(entry.node_id) : Promise.resolve(null)),
    enabled: !!entry?.node_id,
  });

  // ⑤ 收件箱
  const { data: inbox } = useQuery({
    queryKey: ["diary", "inbox"],
    queryFn: () => diaryApi.inbox(),
    enabled: tab === "inbox",
  });

  const invalidateAll = () => {
    qc.invalidateQueries({ queryKey: ["diary"] });
    qc.invalidateQueries({ queryKey: ["docs"] });
  };

  usePluginEvent("docs.node.created", invalidateAll);
  usePluginEvent("docs.node.updated", invalidateAll);
  usePluginEvent("docs.node.deleted", invalidateAll);

  const saveMut = useMutation({
    mutationFn: ({ id, format, body }: { id: string; format: string; body: string }) =>
      docsApi.saveContent(id, { format, body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["docs"] }),
  });

  const captureMut = useMutation({
    mutationFn: () => diaryApi.capture(),
    onSuccess: () => {
      toast("ok", "已记入收件箱");
      invalidateAll();
    },
    // ★ T17#4 修复：失败不再静默，人话提示（对齐 T19 口径）
    onError: (err: unknown) => {
      const msg =
        err instanceof ApiError
          ? err.detail || err.title
          : err instanceof Error
            ? err.message
            : "随手记失败，请稍后重试";
      toast("danger", msg);
    },
  });

  const consolidateMut = useMutation({
    mutationFn: ({ nodeId, targetDate }: { nodeId: string; targetDate: string }) =>
      diaryApi.consolidate(nodeId, targetDate),
    onSuccess: invalidateAll,
  });

  const shiftMonth = (delta: number) => {
    setViewYm((cur) => {
      let y = cur.year;
      let m = cur.month + delta;
      if (m < 1) {
        m = 12;
        y -= 1;
      } else if (m > 12) {
        m = 1;
        y += 1;
      }
      return { year: y, month: m };
    });
  };

  const shown: DocsNodeDetail | null = detail ?? null;

  const inboxSorted = useMemo(() => inbox?.items ?? [], [inbox]);

  return (
    <div className="diary-root">
      <div className="diary-tabs">
        <button
          type="button"
          className={tab === "entry" ? "active" : ""}
          onClick={() => setTab("entry")}
        >
          日记
        </button>
        <button
          type="button"
          className={tab === "inbox" ? "active" : ""}
          onClick={() => setTab("inbox")}
        >
          收件箱{inbox && inbox.items.length > 0 ? ` (${inbox.items.length})` : ""}
        </button>
        <button
          type="button"
          className="diary-capture"
          onClick={() => captureMut.mutate()}
          disabled={captureMut.isPending}
        >
          ⚡ 随手记
        </button>
      </div>

      {tab === "entry" ? (
        <div className="diary-layout">
          <div className="diary-pane diary-pane-cal">
            <DateNavigator
              year={viewYm.year}
              month={viewYm.month}
              days={monthData?.days ?? []}
              selectedDate={date}
              today={todayLocalStr()}
              onSelect={(d) => setDate(d)}
              onShift={shiftMonth}
            />
          </div>
          <div className="diary-pane diary-pane-viewer">
            {entry && shown ? (
              <DocsViewer
                name={date ?? shown.name}
                format={shown.format ?? "md"}
                body={shown.body ?? ""}
                onSave={(format, body) =>
                  entry && saveMut.mutate({ id: entry.node_id, format, body })
                }
              />
            ) : (
              <div className="diary-empty">← 选择一天，或直接写</div>
            )}
          </div>
        </div>
      ) : (
        <div className="diary-inbox">
          <div className="diary-inbox-hint">记于任何处都行；复盘时点「归纳」把它归到某天。</div>
          {inboxSorted.map((item) => (
            <div key={item.id} className="diary-inbox-row">
              <span className="diary-inbox-name">{item.name}</span>
              <div className="diary-inbox-actions">
                <input
                  type="date"
                  className="diary-consolidate-date"
                  defaultValue={todayLocalStr()}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      consolidateMut.mutate({
                        nodeId: item.id,
                        targetDate: (e.target as HTMLInputElement).value,
                      });
                    }
                  }}
                  aria-label={`归纳 ${item.name} 到某天`}
                />
                <button
                  type="button"
                  onClick={() =>
                    consolidateMut.mutate({
                      nodeId: item.id,
                      targetDate: todayLocalStr(),
                    })
                  }
                  disabled={consolidateMut.isPending}
                >
                  归纳到今天
                </button>
              </div>
            </div>
          ))}
          {inboxSorted.length === 0 && <div className="diary-empty">收件箱是空的</div>}
        </div>
      )}
    </div>
  );
}

export { DiaryApp };
