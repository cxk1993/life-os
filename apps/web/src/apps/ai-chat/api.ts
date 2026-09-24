/**
 * ai-chat 模块数据请求层（E7 TX-AI-CHAT-01 前端块）。
 * 契约：POST /api/v1/ai-chat/messages {text, session_id?} → {session_id, reply, audit, system}。
 */
import { api } from "@/shared/api/client";

export interface ChatReply {
  session_id: string;
  reply: string;
  audit: string[];
  system: string;
}

export const chatApi = {
  send: (text: string, sessionId = "default") =>
    api.post<ChatReply>("/api/v1/ai-chat/messages", { text, session_id: sessionId }),
};
