"""内部 HTTP 转发（T18 ★）：tools/call 的实际执行器。

★ 铁律（ADR-0002）：**严禁 import 业务插件模块**。
  MCP tool 调用一律转成一次普通 HTTP 请求，打到「插件自己的 REST 端点」——
  与前端走完全相同的 service 路径（鉴权 / 幂等 / sync_change / WS 推送全复用）。

身份：转发请求带的是**短时 service JWT**（签给 admin，同单用户系统口径）；
  AI 的真实身份（PAT）由调用方（mcp_server）记进 audit_log，不往下游传。
"""
from __future__ import annotations

import os
from typing import Any

import httpx

from core.security import USER_SUB, create_access_token

_DEFAULT_BASE = "http://127.0.0.1:18000"
_TIMEOUT = 15.0


def internal_base() -> str:
    """同进程服务的基址（测试/生产都可覆盖）。"""
    return os.environ.get("INTERNAL_API_BASE", _DEFAULT_BASE)


def forward(
    method: str,
    path: str,
    payload: dict[str, Any] | None,
    transport: httpx.BaseTransport | None = None,
) -> tuple[int, Any]:
    """向插件 REST 端点发一次请求。

    GET：payload 作为查询参数；其余方法：payload 作为 JSON 请求体。
    返回 (HTTP 状态码, 解析后的 JSON 或 None)。非 2xx **不抛异常**——
    把状态码与错误体交回 MCP 层转成 tool 结果（isError），鉴权失败除外
    （鉴权在 require_pat 已做，转发层的 401/403 属于工具执行失败）。

    transport 参数仅供测试注入 httpx.MockTransport（官方测试机制），
    生产调用一律默认 None。
    """
    headers = {"Authorization": f"Bearer {create_access_token(USER_SUB)}"}
    with httpx.Client(
        base_url=internal_base(), timeout=_TIMEOUT, transport=transport
    ) as client:
        if method == "GET":
            resp = client.get(path, params=payload or None, headers=headers)
        else:
            resp = client.request(method, path, json=payload or {}, headers=headers)
    if resp.status_code == 204 or not resp.content:
        return resp.status_code, None
    try:
        return resp.status_code, resp.json()
    except ValueError:
        # 非 JSON（如 HTML 错误页）→ 原样截断当文本，绝不静默丢内容。
        return resp.status_code, {"raw": resp.text[:500]}
