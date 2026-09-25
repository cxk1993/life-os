"""MCP server 核心（T18 §C）：把 JSON-RPC 消息分发到 tools。

★ 传输形态说明（与任务卡差异的备案，详见 docs/verify/T18-report.md）：
  任务卡建议直接用官方 SDK 的 StreamableHTTPServerTransport。实测它需要
  持有 app lifespan 控制权（`async with session_manager.run()`），而插件框架
  （ModuleRegistry.mount → include_router）不向插件提供 lifespan —— 结构性冲突。
  故本模块实现 MCP Streamable HTTP 规范允许的 **stateless request-response 子集**：
    - POST：JSON-RPC 请求 → application/json 单响应（客户端 Accept 本就含它）
    - notifications/* → 202 Accepted（无 body）
    - GET（SSE 推送流）/ DELETE（会话终止）→ 405（规范明文允许："server that
      does not offer SSE ... MUST return 405"）
  协议互操作由**官方 MCP SDK 客户端**在 verify 脚本里实测握手保证。
  本模块零业务词：工具映射全部经 registry_adapter 动态读出。

工具执行（tools/call）：
  1. registry_adapter.find_tool(name) —— 未知工具 → JSON-RPC error -32602
  2. ensure_scope(pat, tool.scope) —— 越权 → HTTP 403（内核 problem+json）
  3. forward(tool.method, tool.path, payload) —— 内部 HTTP，不 import 插件
  4. 写类工具 → audit_call / 拒绝 → audit_denied
"""
from __future__ import annotations

import json
from typing import Any

from core.errors import ForbiddenError

from . import audit
from .auth import PatContext, ensure_scope
from .external import call_external, external_tools, find_external
from .forward import forward
from .registry_adapter import build_tool_map, find_tool, is_write_tool

SERVER_NAME = "lifeos-mcp"
SERVER_VERSION = "0.1.0"
# 我们支持的协议版本（核心三原语在各版本间一致；握手时回客户端所请求的版本）。
_SUPPORTED_PROTOCOL_VERSIONS = ("2024-11-05", "2025-03-26", "2025-06-18")
_DEFAULT_PROTOCOL_VERSION = "2025-06-18"

# JSON-RPC 错误码（标准）
_ERR_METHOD_NOT_FOUND = -32601
_ERR_INVALID_PARAMS = -32602
_ERR_INTERNAL = -32603


def _rpc_error(code: int, message: str, msg_id: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def _rpc_result(result: dict[str, Any], msg_id: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _tool_schema() -> dict[str, Any]:
    """最小可行 inputSchema：单个 payload 对象（GET 时转查询参数）。"""
    return {
        "type": "object",
        "properties": {
            "payload": {
                "type": "object",
                "additionalProperties": True,
                "description": (
                    "请求内容。写类工具=JSON 请求体；读类工具=查询参数（如 filter/from/to）。"
                ),
            }
        },
    }


def _handle_initialize(msg: dict[str, Any], msg_id: Any) -> dict[str, Any]:
    params = msg.get("params") or {}
    client_version = params.get("protocolVersion")
    version = (
        client_version
        if client_version in _SUPPORTED_PROTOCOL_VERSIONS
        else _DEFAULT_PROTOCOL_VERSION
    )
    return _rpc_result(
        {
            "protocolVersion": version,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        },
        msg_id,
    )


def _handle_tools_list(msg_id: Any) -> dict[str, Any]:
    tools = [
        {
            "name": t.name,
            "description": t.description,
            "inputSchema": _tool_schema(),
        }
        for t in build_tool_map()
    ]
    # 外部 MCP 源（BeeCount 等）：未配置则空，不挡本地工具。
    for t in external_tools():
        tools.append(
            {
                "name": t.name,
                "description": t.description,
                "inputSchema": _tool_schema(),
            }
        )
    return _rpc_result({"tools": tools}, msg_id)


def _handle_tools_call(msg: dict[str, Any], msg_id: Any, pat: PatContext) -> dict[str, Any]:
    params = msg.get("params") or {}
    name = str(params.get("name", ""))
    arguments = params.get("arguments") or {}
    ext = find_external(name)
    if ext is not None:
        try:
            ensure_scope(pat, ext.scope)
        except ForbiddenError:
            audit.audit_denied(
                token_prefix=pat.token_prefix, tool_name=name, reason=f"缺 scope {ext.scope}"
            )
            raise
        payload_ext = arguments.get("payload") if isinstance(arguments, dict) else None
        if not isinstance(payload_ext, dict):
            payload_ext = {}
        ok, body = call_external(ext, payload_ext)
        if ext.is_write:
            audit.audit_call(
                token_prefix=pat.token_prefix,
                tool_name=ext.name,
                method="MCP",
                path=ext.upstream,
                payload=payload_ext,
            )
        text = json.dumps(body, ensure_ascii=False, default=str)
        return _rpc_result(
            {"content": [{"type": "text", "text": text}], "isError": not ok},
            msg_id,
        )
    tool = find_tool(name)
    if tool is None:
        # 未知工具也记一条拒绝（是谁在试探工具边界，可追溯）。
        audit.audit_denied(
            token_prefix=pat.token_prefix, tool_name=name or "（空）", reason="未知工具"
        )
        return _rpc_error(_ERR_INVALID_PARAMS, f"未知工具：{name}", msg_id)

    # scope 越权 → HTTP 403 problem+json（任务卡 §D.5 明确口径），同时落审计。
    try:
        ensure_scope(pat, tool.scope)
    except ForbiddenError:
        audit.audit_denied(
            token_prefix=pat.token_prefix, tool_name=name, reason=f"缺 scope {tool.scope}"
        )
        raise

    payload = arguments.get("payload") if isinstance(arguments, dict) else None
    if not isinstance(payload, dict):
        payload = None

    status, body = forward(tool.method, tool.path, payload)
    ok = 200 <= status < 300

    if is_write_tool(tool):
        audit.audit_call(
            token_prefix=pat.token_prefix,
            tool_name=tool.name,
            method=tool.method,
            path=tool.path,
            payload=payload,
        )

    text = json.dumps(
        {"status": status, "body": body},
        ensure_ascii=False,
        default=str,
    )
    return _rpc_result(
        {
            "content": [{"type": "text", "text": text}],
            "isError": not ok,
        },
        msg_id,
    )


def handle_message(msg: dict[str, Any], pat: PatContext) -> dict[str, Any] | None:
    """处理一条 JSON-RPC 消息。

    返回响应 dict（请求）；notification 返回 None（→ 202）。
    """
    if msg.get("jsonrpc") != "2.0":
        return _rpc_error(_ERR_INVALID_PARAMS, "jsonrpc 字段必须为 \"2.0\"", msg.get("id"))
    method = str(msg.get("method", ""))
    msg_id = msg.get("id")

    # notification（无 id）按规范不回响应；notifications/* 一律 202。
    if msg_id is None or method.startswith("notifications/"):
        return None

    try:
        if method == "initialize":
            return _handle_initialize(msg, msg_id)
        if method == "ping":
            return _rpc_result({}, msg_id)
        if method == "tools/list":
            return _handle_tools_list(msg_id)
        if method == "tools/call":
            return _handle_tools_call(msg, msg_id, pat)
        return _rpc_error(_ERR_METHOD_NOT_FOUND, f"未知方法：{method}", msg_id)
    except ForbiddenError:
        raise  # 越权要走 HTTP 403，不在 JSON-RPC body 里掩饰
    except Exception as exc:  # noqa: BLE001 —— 转成 JSON-RPC 内部错误，不静默
        return _rpc_error(_ERR_INTERNAL, f"工具执行失败：{exc}", msg_id)
