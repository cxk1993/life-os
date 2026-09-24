import { useState } from "react";

import { ApiError } from "@/shared/api/client";
import { chatApi } from "./api";
import type { ChatReply } from "./api";

/**
 * E7 · TX-AI-CHAT-01 · 内置 AI 对话窗（前端 UI 块）。
 *
 * 契约（MiMo 网关进仓）：POST /api/v1/ai-chat/messages
 *   {text, session_id} → {session_id, reply, audit, system}
 *   StubGateway 默认（未配 model-gateway 时明说不假成功）；EchoGateway 联调回显。
 *
 * UI：消息列表（用户/助手气泡）+ 输入区 + 发送；审计折叠（工具调用轨迹）；错误可区分。
 */
interface Msg {
  role: "user" | "assistant";
  text: string;
  error?: boolean;
}

export default function ChatApp() {
  const [messages, setMessages] = useState<Msg[]>([
    { role: "assistant", text: "你好，我是内置 AI 助手。可以直接问我日程、待办相关的问题。" },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [audit, setAudit] = useState<string[]>([]);
  const [showAudit, setShowAudit] = useState(false);

  const send = async () => {
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setBusy(true);
    setMessages((m) => [...m, { role: "user", text }]);
    try {
      const r: ChatReply = await chatApi.send(text);
      setMessages((m) => [...m, { role: "assistant", text: r.reply }]);
      setAudit(r.audit ?? []);
    } catch (e) {
      const err =
        e instanceof ApiError && e.status >= 500
          ? "暂时不可用（网关未就绪或服务异常）"
          : "发送失败，请稍后再试";
      setMessages((m) => [...m, { role: "assistant", text: err, error: true }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="chat-app" data-testid="chat-app">
      <div className="chat-app__msgs" data-testid="chat-msgs" role="log" aria-live="polite">
        {messages.map((m, i) => (
          <div key={i} className={`chat-app__msg is-${m.role}${m.error ? " is-error" : ""}`}>
            <div className="chat-app__bubble">{m.text}</div>
          </div>
        ))}
        {busy ? (
          <div className="chat-app__msg is-assistant">
            <div className="chat-app__bubble">…</div>
          </div>
        ) : null}
      </div>
      {audit.length > 0 ? (
        <div className="chat-app__audit">
          <button
            type="button"
            className="chat-app__audit-toggle"
            onClick={() => setShowAudit((v) => !v)}
          >
            {showAudit ? "收起工具轨迹" : `查看工具轨迹（${audit.length}）`}
          </button>
          {showAudit ? (
            <ul className="chat-app__audit-list" data-testid="chat-audit">
              {audit.map((a, i) => (
                <li key={i}>{a}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
      <div className="chat-app__input">
        <input
          type="text"
          value={input}
          placeholder="问点什么…（Enter 发送）"
          aria-label="对话输入"
          data-testid="chat-input"
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) void send();
          }}
          disabled={busy}
        />
        <button
          type="button"
          className="chat-app__send"
          onClick={() => void send()}
          disabled={!input.trim() || busy}
          aria-label="发送"
          data-testid="chat-send"
        >
          发送
        </button>
      </div>
    </div>
  );
}
