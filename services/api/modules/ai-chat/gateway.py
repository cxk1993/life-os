"""ai_chat · LLM 网关适配（可插拔）。

V1：stub 明确「未配置」不假成功；
接 model-gateway 时实现 complete()，带 tools 注入与 finish_reason 分支。
"""
from __future__ import annotations

from typing import Any, Protocol

# 注：ChatTurn 以鸭子类型协作（避免包内相对导入在独立加载时失败）


class LLMGateway(Protocol):
    def complete(self, system: str, turns: list[Any], tools: list[dict[str, Any]]) -> Any: ...


class StubGateway:
    def complete(self, system: str, turns: list[Any], tools: list[dict[str, Any]]) -> Any:
        from .chat_loop import ChatTurn

        return ChatTurn(
            "assistant",
            text="AI 网关未配置（model-gateway）。已就绪的 system 长度="
            + str(len(system))
            + "，白名单工具="
            + str(len(tools)),
        )


class EchoGateway:
    """联调用：不调真 LLM，回显最后一句（前端/循环可测）。"""

    def complete(self, system: str, turns: list[Any], tools: list[dict[str, Any]]) -> Any:
        from .chat_loop import ChatTurn

        last = next((t.text for t in reversed(turns) if getattr(t, "role", "") == "user"), "")
        return ChatTurn("assistant", text=f"echo:{last}")


class ModelGateway:
    """接 model-gateway（OpenAI 兼容 tool calling）。

    环境：AI_CHAT_BASE_URL / AI_CHAT_API_KEY / AI_CHAT_MODEL
    超时 30s；失败抛给循环侧（不假成功）。
    """

    def complete(self, system: str, turns: list[Any], tools: list[dict[str, Any]]) -> Any:
        import json

        import httpx

        from .chat_loop import ChatTurn

        from core.config import read_setting

        base = (read_setting("AI_CHAT_BASE_URL", "") or "").rstrip("/")
        key = read_setting("AI_CHAT_API_KEY", "") or ""
        model = read_setting("AI_CHAT_MODEL", "deepseek-v4-flash") or "deepseek-v4-flash"
        if not base:
            return ChatTurn("assistant", text="AI_CHAT_BASE_URL 未配置（model-gateway）")
        msgs: list[dict[str, Any]] = [{"role": "system", "content": system}]
        for t in turns:
            if t.role == "user":
                msgs.append({"role": "user", "content": t.text})
            elif t.role == "assistant":
                msgs.append({"role": "assistant", "content": t.text})
            elif t.role == "tool":
                msgs.append(
                    {
                        "role": "tool",
                        "tool_call_id": t.tool_name or "t",
                        "content": json.dumps(t.tool_result or {}, ensure_ascii=False)[:2000],
                    }
                )
        body: dict[str, Any] = {"model": model, "messages": msgs}
        if tools:
            body["tools"] = tools
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        r = httpx.post(f"{base}/chat/completions", json=body, headers=headers, timeout=30.0)
        r.raise_for_status()
        data = r.json()
        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        tcs = msg.get("tool_calls") or []
        if tcs:
            tc = tcs[0]
            fn = tc.get("function") or {}
            args = fn.get("arguments") or "{}"
            try:
                parsed = json.loads(args) if isinstance(args, str) else args
            except Exception:
                parsed = {}
            return ChatTurn("assistant", tool_name=fn.get("name"), tool_args=parsed)
        return ChatTurn("assistant", text=str(msg.get("content") or ""))


def get_gateway() -> LLMGateway:
    from core.config import read_setting

    mode = (read_setting("AI_CHAT_GATEWAY", "stub") or "stub").strip().lower()
    if mode == "echo":
        return EchoGateway()
    if mode in ("model", "model-gateway", "openai"):
        return ModelGateway()
    return StubGateway()
