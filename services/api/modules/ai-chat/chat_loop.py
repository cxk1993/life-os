"""TX-AI-CHAT-01 · 内置 AI 对话窗后端骨架（tool_call 循环）。

安全：token 不进日志全文；工具白名单；max_hops 防环。
LLM 网关可插拔（默认 stub，接 model-gateway 另配）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable

ALLOWED_TOOLS: set[str] = {
    "calendar_event_read",
    "todo_item_read",
    "todo_item_write",
    "notes_search",
    "health_record_read",
    "dashboard_today_read",
}


@dataclass
class ChatTurn:
    role: str
    text: str = ""
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    tool_result: dict[str, Any] | None = None


@dataclass
class ChatSession:
    turns: list[ChatTurn] = field(default_factory=list)
    audit: list[str] = field(default_factory=list)


def build_system(today: date | None = None) -> str:
    d = (today or date.today()).isoformat()
    return f"你是 Life-OS 助手。今天是 {d}。只使用已注册工具；无法完成时明说。"


def run_tool_call_loop(
    user_text: str,
    llm: Callable[[list[ChatTurn]], ChatTurn],
    tools: dict[str, Callable[[dict[str, Any]], dict[str, Any]]],
    *,
    max_hops: int = 4,
) -> ChatSession:
    s = ChatSession()
    s.turns.append(ChatTurn("user", text=user_text))
    for _ in range(max_hops):
        reply = llm(s.turns)
        if reply.tool_name is None:
            s.turns.append(ChatTurn("assistant", text=reply.text))
            s.audit.append("final")
            return s
        name = reply.tool_name
        if name not in ALLOWED_TOOLS:
            s.turns.append(ChatTurn("assistant", text=f"工具 {name} 不在白名单"))
            s.audit.append(f"denied:{name}")
            return s
        fn = tools.get(name)
        if not fn:
            s.turns.append(ChatTurn("assistant", text="工具未实现"))
            s.audit.append(f"missing:{name}")
            return s
        args = reply.tool_args or {}
        result = fn(args)
        s.audit.append(f"call:{name}")
        s.turns.append(ChatTurn("tool", tool_name=name, tool_args=args, tool_result=result))
    s.turns.append(ChatTurn("assistant", text="步骤过多，请拆成更小的问题。"))
    s.audit.append("max_hops")
    return s
