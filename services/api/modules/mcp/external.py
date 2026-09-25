"""通用外部 MCP 源桥（TX-MCP-EXT · 零业务词）。

任何 Streamable HTTP MCP 服务都可经环境变量挂进 tools/list：
  EXTERNAL_MCP_URL          端点（如自有云的 /api/v1/mcp）
  EXTERNAL_MCP_TOKEN        Bearer PAT（只读 env，不回显）
  EXTERNAL_MCP_PREFIX       工具名前缀（如 beecount）
  EXTERNAL_MCP_TOOLS        逗号分隔的上游工具名（read）
  EXTERNAL_MCP_WRITE_TOOLS  逗号分隔的写工具（默认不暴露）
  EXTERNAL_MCP_ALLOW_WRITE  1 才暴露写并放行

★ 未配置 → 空表，不影响本地工具（fail-soft）。
★ ADR-0004：与外部 MCP 的往来只在本文件。
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from core.config import read_setting

log = logging.getLogger("mcp.external")

_TIMEOUT = 20.0


def _setting(key: str, default: str = "") -> str:
    return (read_setting(key, default) or "").strip()


def configured() -> bool:
    return bool(_setting("EXTERNAL_MCP_URL") and _setting("EXTERNAL_MCP_TOKEN"))


def _allow_write() -> bool:
    return _setting("EXTERNAL_MCP_ALLOW_WRITE", "0").lower() in ("1", "true", "yes", "on")


def _prefix() -> str:
    p = _setting("EXTERNAL_MCP_PREFIX", "ext")
    return p or "ext"


@dataclass(frozen=True)
class ExternalTool:
    name: str
    upstream: str
    description: str
    scope: str
    is_write: bool


def _split(raw: str) -> list[str]:
    return [x.strip() for x in raw.split(",") if x.strip()]


def external_tools() -> list[ExternalTool]:
    if not configured():
        return []
    prefix = _prefix()
    out: list[ExternalTool] = []
    for up in _split(_setting("EXTERNAL_MCP_TOOLS")):
        out.append(
            ExternalTool(
                name=f"{prefix}_{up}",
                upstream=up,
                description=f"external MCP · {up}（read）",
                scope=f"{prefix}:read",
                is_write=False,
            )
        )
    if _allow_write():
        for up in _split(_setting("EXTERNAL_MCP_WRITE_TOOLS")):
            out.append(
                ExternalTool(
                    name=f"{prefix}_{up}",
                    upstream=up,
                    description=f"external MCP · {up}（write）",
                    scope=f"{prefix}:write",
                    is_write=True,
                )
            )
    return out


def find_external(name: str) -> ExternalTool | None:
    for t in external_tools():
        if t.name == name:
            return t
    return None


def _rpc(method: str, params: dict[str, Any] | None, msg_id: int = 1) -> dict[str, Any]:
    url = _setting("EXTERNAL_MCP_URL")
    token = _setting("EXTERNAL_MCP_TOKEN")
    if not url or not token:
        raise RuntimeError("external MCP not configured")
    payload = {"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params or {}}
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        try:
            return resp.json()
        except ValueError:
            for line in resp.text.splitlines():
                if line.startswith("data:"):
                    return json.loads(line[5:].strip())
            raise RuntimeError("external MCP response unparsable") from None


def call_external(tool: ExternalTool, arguments: dict[str, Any]) -> tuple[bool, Any]:
    if tool.is_write and not _allow_write():
        return False, {"error": "write tools disabled"}
    try:
        data = _rpc("tools/call", {"name": tool.upstream, "arguments": arguments}, msg_id=2)
    except Exception as exc:  # noqa: BLE001
        log.warning("external tools/call failed: %s", exc)
        return False, {"error": str(exc)}
    if isinstance(data, dict) and data.get("error"):
        return False, data["error"]
    result = data.get("result") if isinstance(data, dict) else None
    return True, result
