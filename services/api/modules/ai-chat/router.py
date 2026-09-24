"""ai_chat 路由：health + messages（tool_call 循环）。"""
import json
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from core.deps import get_current_user

from .chat_loop import ChatSession, ChatTurn, build_system, run_tool_call_loop
from .gateway import get_gateway

router = APIRouter()

_MANIFEST_PATH = Path(__file__).resolve().parent / "manifest.json"
with _MANIFEST_PATH.open(encoding="utf-8") as _f:
    _MANIFEST = json.load(_f)

# 内存会话（V1 零新表）
_SESSIONS: dict[str, ChatSession] = {}


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    session_id: str = Field(default="default", max_length=64)


def _gateway_llm(turns: list[ChatTurn]) -> ChatTurn:
    """走 AI_CHAT_GATEWAY（stub/echo/…）；未配置时 stub 明确说，不假成功。"""
    return get_gateway().complete(build_system(), turns, [])


@router.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@router.get("/manifest")
def manifest() -> dict:
    return _MANIFEST


@router.post("/messages")
def post_message(
    body: MessageIn,
    _user: Annotated[Any, Depends(get_current_user)] = None,
) -> dict[str, Any]:
    s = _SESSIONS.setdefault(body.session_id, ChatSession())
    out = run_tool_call_loop(body.text, _gateway_llm, {})
    # 合并到会话
    s.turns.extend(out.turns)
    s.audit.extend(out.audit)
    last = next((t.text for t in reversed(out.turns) if t.role == "assistant"), "")
    return {
        "session_id": body.session_id,
        "reply": last,
        "audit": list(out.audit),
        "system": build_system(),
    }
