"""内部 HTTP 转发（T18 ★）：tools/call 的实际执行器。

★ 铁律（ADR-0002）：**严禁 import 业务插件模块**。
  MCP tool 调用一律转成一次普通 HTTP 请求，打到「插件自己的 REST 端点」——
  与前端走完全相同的 service 路径（鉴权 / 幂等 / sync_change / WS 推送全复用）。

身份：转发请求带的是**短时 service JWT**（签给 admin，同单用户系统口径）；
  AI 的真实身份（PAT）由调用方（mcp_server）记进 audit_log，不往下游传。
"""
from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import quote

import httpx

from core.mcp_writes import CLIENT_MCP
from core.mcp_writes import HEADER as _CLIENT_HEADER
from core.security import USER_SUB, create_access_token

_DEFAULT_BASE = "http://127.0.0.1:18000"
_TIMEOUT = 15.0

# ★ 2026-09-27（主人「把挂路径参数的整类端点修通」）：路径参数占位符。
#   工具面是**机械推导**出来的，manifest 里写的是 OpenAPI 原样的 path（含 `{x}`）；
#   不代入就只能打到字面量 `{x}` → 404。故在桥接层做替换。
_PATH_PARAM_RE = re.compile(r"\{([^{}/]+)\}")


def _substitute_path_params(
    path: str, payload: dict[str, Any] | None
) -> tuple[str, dict[str, Any], list[str]]:
    """把路径里的 `{name}` 用 payload 的同名值代入，并从 body 里摘掉这些键。

    返回 (新路径, 剩余 payload, 缺失的参数名列表)。
    ★ 值会做 URL 转义（`quote(safe="")`）—— 否则参数里带个 `/` 就能拼出跨段路径。
    ★ 缺参数**不静默**：由调用方转成明确 422，而不是打出去 404 让人猜。
    """
    body = dict(payload or {})
    missing: list[str] = []
    for name in _PATH_PARAM_RE.findall(path or ""):
        if name in body and body[name] is not None:
            path = path.replace("{" + name + "}", quote(str(body.pop(name)), safe=""))
        else:
            missing.append(name)
    return path, body, missing


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
    path, body, missing = _substitute_path_params(path, payload)
    if missing:
        return 422, {
            "type": "about:blank",
            "title": "缺少路径参数",
            "status": 422,
            "detail": f"该工具路径需要参数 {missing}，请在 payload 里给出",
            "path_template": path,
        }
    # ★ 2026-10-02（主人「MCP 创建待办时强制加标签」）：
    #   打来源标记 —— 插件据此判定「这是 AI 来路」，从而施加比人更严的写约束
    #（见 core/mcp_writes.py 的来龙去脉）。人对前端的操作**一点不受影响**。
    headers = {
        "Authorization": f"Bearer {create_access_token(USER_SUB)}",
        _CLIENT_HEADER: CLIENT_MCP,
    }
    with httpx.Client(
        base_url=internal_base(), timeout=_TIMEOUT, transport=transport
    ) as client:
        if method == "GET":
            resp = client.get(path, params=body or None, headers=headers)
        else:
            resp = client.request(method, path, json=body, headers=headers)
    if resp.status_code == 204 or not resp.content:
        return resp.status_code, None
    try:
        return resp.status_code, resp.json()
    except ValueError:
        # 非 JSON（如 HTML 错误页）→ 原样截断当文本，绝不静默丢内容。
        return resp.status_code, {"raw": resp.text[:500]}
