"""★ 从模块 OpenAPI 提取"精确工具参数"（astrbot 2026-09-26 · 主人令「改进可改进点」）

**为什么**：原先 `tools/list` 的 `inputSchema` 只有个通用 `payload` 对象
（`additionalProperties: true`）—— AI **不知道能传什么字段**，只能"猜"
（实证：pi 查倒计时时"试了三种方式"）。

**怎么做**：内核已提供**模块级 openapi**（`/api/{module_id}/openapi.json`，
见 core/app.py 乙案·总监令 92/95）。本模块据此提取每个端点的参数，
生成**具名属性**的 inputSchema；**拉不到则降级回通用 payload**（绝不报错）。

设计纪律：
- **进程内缓存**（按 module_id）：MCP 工具列表会被频繁拉取，不能每次都打 HTTP；
- **短超时 + 全兜底**：任何异常 → 返回 {} → 调用方降级；
- **不 import 业务插件**（与 registry_adapter 同纪律，只走 HTTP）。
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from .forward import internal_base

log = logging.getLogger("mcp.openapi_params")

_TIMEOUT = 3.0
# module_id -> {(METHOD, path): params_schema}
_CACHE: dict[str, dict[tuple[str, str], dict[str, Any]]] = {}


def _type_map(t: str | None) -> dict[str, Any]:
    """OpenAPI 类型 → JSON Schema 片段（保守，未知按 string）。"""
    if t == "integer":
        return {"type": "integer"}
    if t == "number":
        return {"type": "number"}
    if t == "boolean":
        return {"type": "boolean"}
    if t == "array":
        return {"type": "array", "items": {"type": "string"}}
    if t == "object":
        return {"type": "object"}
    return {"type": "string"}


def _load_module(module_id: str) -> dict[tuple[str, str], dict[str, Any]]:
    """拉某模块的 openapi，摊平成 {(METHOD, path): {字段名: schema}}。失败返回 {}。"""
    if module_id in _CACHE:
        return _CACHE[module_id]

    out: dict[tuple[str, str], dict[str, Any]] = {}
    try:
        url = f"{internal_base()}/api/{module_id}/openapi.json"
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.get(url)
        if resp.status_code == 200:
            spec = resp.json()
            for path, ops in (spec.get("paths") or {}).items():
                if not isinstance(ops, dict):
                    continue
                for method, op in ops.items():
                    if not isinstance(op, dict):
                        continue
                    props: dict[str, Any] = {}
                    required: list[str] = []
                    # ① 查询/路径参数
                    for prm in op.get("parameters") or []:
                        if not isinstance(prm, dict):
                            continue
                        name = prm.get("name")
                        if not name or prm.get("in") == "path":
                            continue  # path 参数由调用方在 URL 里给，不暴露
                        frag = _type_map((prm.get("schema") or {}).get("type"))
                        if prm.get("description"):
                            frag["description"] = prm["description"]
                        props[name] = frag
                        if prm.get("required"):
                            required.append(name)
                    # ② 请求体（JSON）
                    body = ((op.get("requestBody") or {}).get("content") or {}).get(
                        "application/json"
                    )
                    if isinstance(body, dict):
                        sch = body.get("schema") or {}
                        for k, v in (sch.get("properties") or {}).items():
                            frag = _type_map((v or {}).get("type"))
                            if (v or {}).get("description"):
                                frag["description"] = v["description"]
                            props[k] = frag
                        required.extend(
                            k for k in (sch.get("required") or []) if k in props
                        )
                    if props:
                        entry: dict[str, Any] = {"properties": props}
                        if required:
                            entry["required"] = sorted(set(required))
                        out[(method.upper(), path)] = entry
    except Exception as exc:  # noqa: BLE001 —— 拉不到就降级，绝不阻断
        log.info("模块 %s 的 openapi 拉取失败（降级为通用 payload）：%s", module_id, exc)

    _CACHE[module_id] = out
    return out


def params_for(module_id: str, method: str, path: str) -> dict[str, Any]:
    """取某端点的参数描述。返回 {} 表示"无信息，请降级"。"""
    try:
        return _load_module(module_id).get((method.upper(), path), {})
    except Exception:  # noqa: BLE001
        return {}


def clear_cache() -> None:
    """清缓存（测试用）。"""
    _CACHE.clear()
