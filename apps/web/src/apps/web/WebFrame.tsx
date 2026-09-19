/**
 * 内嵌窗口：把一个网页装进 Life-OS。
 *
 * ★ 不许硬编码任何具体站点 —— 本组件只认 entry.url。
 *
 * ── 关于"能不能内嵌"的诚实说明（重要） ─────────────────────────────
 *  浏览器**无法**用 JS 判断一个跨域 iframe 是否被 X-Frame-Options / CSP 拒绝：
 *  被拒时 onLoad 照样会触发，而 contentDocument 因跨域读不到，拿不到任何信号。
 *  可选的"服务端预探测"我们**故意不做** —— 那等于让后端去 fetch 用户填的任意 URL，
 *  是一个 SSRF 口子，与"任意网页"的白名单需求冲突，得不偿失。
 *  所以采用两条**兜底**，保证任何情况下都不是死路：
 *    1) 加载超时（6s）→ 显示"无法内嵌"提示 + 新窗口按钮；
 *    2) 底部常驻一条极简提示 + 工具条里的「在新窗口打开」始终可用。
 *  代价：被拒的站点若加载很快，用户会先看到空白（但有常驻提示可点），不会被困住。
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/shared/components/Button";
import type { WebEntry } from "./api";

/** 加载超时（毫秒）——超过即认为"内嵌不成功"。 */
export const FRAME_TIMEOUT_MS = 6000;

type Phase = "loading" | "ok" | "timeout";

interface Props {
  entry: WebEntry;
}

export default function WebFrame({ entry }: Props) {
  const [phase, setPhase] = useState<Phase>("loading");
  const [nonce, setNonce] = useState(0);
  const timerRef = useRef<number | null>(null);

  // 换条目 / 手动刷新 → 重走加载流程
  useEffect(() => {
    setPhase("loading");
    if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(() => {
      setPhase((p) => (p === "loading" ? "timeout" : p));
    }, FRAME_TIMEOUT_MS);
    return () => {
      if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    };
  }, [entry.url, nonce]);

  const onLoad = useCallback(() => {
    if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    setPhase("ok");
  }, []);

  const openExternal = useCallback(() => {
    window.open(entry.url, "_blank", "noopener,noreferrer");
  }, [entry.url]);

  const copyUrl = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(entry.url);
    } catch {
      /* 剪贴板不可用时静默（不是关键路径） */
    }
  }, [entry.url]);

  // ★ sandbox 说明：allow-scripts + allow-same-origin 同时给，浏览器会有安全告警
  //   （理论上被嵌页面可自解除 sandbox）。但被嵌页面与本应用**跨源**，
  //   且我们**不给** allow-top-navigation，拿不到顶层导航能力；
  //   而 SPA 类站点（Flutter/React 打包产物）少这两个直接白屏。
  //   这是"能跑通"与"理论纯洁"之间的**已知权衡**，不是疏忽。
  const sandbox = "allow-scripts allow-same-origin allow-forms allow-popups allow-downloads";

  const title = useMemo(() => entry.title || entry.slug, [entry.title, entry.slug]);

  return (
    <div className="web-frame">
      <div className="web-frame__bar">
        <span className="web-frame__title" title={title}>
          {title}
        </span>
        <span className="web-frame__url" title={entry.url}>
          {entry.url}
        </span>
        <span className="web-frame__spacer" />

        <Button onClick={() => setNonce((n) => n + 1)} title="重新加载">
          刷新
        </Button>
        <Button onClick={openExternal} title="在浏览器新标签打开（内嵌失败时的退路）">
          在新窗口打开
        </Button>
        <Button onClick={copyUrl} title="复制地址">
          复制地址
        </Button>
        {/* ★ 这两个按钮是"接口预留"：窗口能力（置顶 / 固定几何）属 T22 领地 */}
        <Button disabled title="待 T22 窗口能力">
          ⭐ 置顶
        </Button>
        <Button disabled title="待 T22 窗口能力">
          📌 固定几何
        </Button>
      </div>

      <div className="web-frame__body">
        <iframe
          key={`${entry.id}-${nonce}`}
          className="web-frame__iframe"
          src={entry.url}
          title={title}
          sandbox={sandbox}
          referrerPolicy="no-referrer"
          onLoad={onLoad}
        />

        {phase === "loading" && (
          <div className="web-frame__overlay">
            <div className="web-frame__overlay-text">正在加载…</div>
          </div>
        )}

        {phase === "timeout" && (
          <div className="web-frame__overlay web-frame__overlay--solid">
            <div className="web-frame__overlay-text">
              <strong>没能内嵌这个网页</strong>
              <p>可能是该站点禁止被嵌入（X-Frame-Options / CSP），或网络不通。</p>
            </div>
            <div className="web-frame__overlay-actions">
              <Button variant="primary" onClick={openExternal}>
                在新窗口打开
              </Button>
              <Button onClick={() => setNonce((n) => n + 1)}>重试</Button>
            </div>
          </div>
        )}
      </div>

      {/* ★ 常驻兜底：浏览器拿不到"被拒"信号，所以留一条随时可点的出路 */}
      <div className="web-frame__hint">
        画面空白？该站点可能禁止被嵌入 ——
        <button type="button" className="web-frame__link" onClick={openExternal}>
          在新窗口打开 ↗
        </button>
      </div>
    </div>
  );
}
