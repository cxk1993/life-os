"""TX-AI-CHAT-01 · E7 工具桥：MCP 白名单工具 → 内部 API（声明即授权）。

★ 2026-09-26 hermes 接线（生产实测根因驱动）：
  tools 此前恒为 []（gateway.complete(..., []) 与 loop(..., {})），
  LLM 拿不到工具 schema，只能凭 system 字面「只使用已注册工具」**幻觉**
  ——本机探针实锤：真实 2 条事件 → AI 答「无日程事件」（audit=['final']）。

桥 = 既有 InternalHttpClient（ISSUE-005 A 案）：
  capability 白名单与 manifest.requires 一一对应，get_plugin_client
  机器校验 ⊆ requires（越权 403）——零新鉴权流程，作用域受限。
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

from fastapi import Request

from core.deps import get_plugin_client

# 工具 → 能力（与 manifest.requires 严格一致）
_CAPS = [
    "calendar.event.read",
    "todo.item.read",
    "health.record.read",
    "dashboard.today.read",
]


def build_tool_defs() -> list[dict[str, Any]]:
    """OpenAI function-calling schema。参数名与 MCP 目录逐字一致（from/to 带连字符键）。"""
    return [
        {
            "type": "function",
            "function": {
                "name": "calendar_event_read",
                "description": (
                    "读取日程事件。不传 from/to 时自动限定为【今天】（CST 00:00–24:00）。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "from": {
                            "type": "string",
                            "description": "ISO8601 起点（可选，默认今天 00:00）",
                        },
                        "to": {
                            "type": "string",
                            "description": "ISO8601 终点（可选，默认明天 00:00）",
                        },
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "todo_item_read",
                "description": "读取待办列表（默认未完成项，≤20 条）。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "enum": ["done", "todo", "all"],
                            "description": "默认 todo",
                        },
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "health_record_read",
                "description": "读取健康记录（症状/用药/预约/化验，≤20 条）。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "kind": {
                            "type": "string",
                            "description": "symptom|medication|appointment|lab（可选）",
                        },
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "dashboard_today_read",
                "description": "读取今日合并视图（日程数/待办/习惯完成度）。",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
    ]


def _today_window() -> dict[str, str]:
    cst = timezone(timedelta(hours=8))
    now = datetime.now(cst)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return {
        "from": start.astimezone(UTC).isoformat(),
        "to": end.astimezone(UTC).isoformat(),
    }


def _cst_today_iso() -> str:
    """CST（主人时区）口径的今天 —— 与 _today_window 同一基准，防 UTC 跨日错杀。"""
    return datetime.now(timezone(timedelta(hours=8))).date().isoformat()


def _window_days(frm: str, to: str) -> int:
    """ISO 区间跨度（天），解析失败按超大窗（→ 强正）。"""
    try:
        a = datetime.fromisoformat(frm.replace("Z", "+00:00"))
        b = datetime.fromisoformat(to.replace("Z", "+00:00"))
        return (b - a).days
    except Exception:  # noqa: BLE001 — 解析不了就是坏窗
        return 9999


def make_tools(request: Request) -> dict[str, Callable[[dict[str, Any]], dict[str, Any]]]:
    client = get_plugin_client(request, _CAPS)

    def calendar_event_read(args: dict[str, Any]) -> dict[str, Any]:
        frm = str(args.get("from") or "")
        to = str(args.get("to") or "")
        want = _today_window()
        today_iso = _cst_today_iso()
        # 只在窗明显离谱时强正为今日（缺参 / 起点在过去 / 窗宽 >31 天）；
        # 「查明天/下周五」等合理未来窗放行，不错杀。
        bad = (
            not frm
            or not to
            or frm[:10] < today_iso
            or _window_days(frm, to) > 31
        )
        if bad:
            frm, to = want["from"], want["to"]
        data = client.get(
            "/api/v1/calendar/events",
            params={"frm": frm, "to": to, "include_children": False, "flat": True},
        )
        items = data if isinstance(data, list) else []
        slim = [
            {
                "title": e.get("title"),
                "start_at": e.get("start_at") or e.get("startAt"),
                "end_at": e.get("end_at") or e.get("endAt"),
            }
            for e in items[:20]
        ]
        return {"ok": True, "count": len(slim), "events": slim, "window": {"from": frm, "to": to}}

    def todo_item_read(args: dict[str, Any]) -> dict[str, Any]:
        status = args.get("status") or "todo"
        data = client.get("/api/v1/todo/items", params={"status": status, "limit": 20})
        items = (data or {}).get("items", [])
        slim = [
            {
                "text": i.get("text"),
                "due_at": i.get("due_at") or i.get("dueAt"),
                "done": i.get("done"),
            }
            for i in items[:20]
        ]
        return {"ok": True, "count": len(slim), "items": slim}

    def health_record_read(args: dict[str, Any]) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if args.get("kind"):
            params["kind"] = args["kind"]
        data = client.get("/api/v1/health/records", params=params)
        items = data if isinstance(data, list) else (data or {}).get("items", [])
        slim = [
            {
                "kind": r.get("kind"),
                "title": r.get("title"),
                "occurred_at": r.get("occurred_at") or r.get("occurredAt"),
            }
            for r in items[:20]
        ]
        return {"ok": True, "count": len(slim), "records": slim}

    def dashboard_today_read(args: dict[str, Any]) -> dict[str, Any]:
        data = client.get("/api/v1/dashboard/today")
        return {"ok": True, "today": data}

    return {
        "calendar_event_read": calendar_event_read,
        "todo_item_read": todo_item_read,
        "health_record_read": health_record_read,
        "dashboard_today_read": dashboard_today_read,
    }
