"""进程内事件总线 + SSE 订阅。

事件格式固定：{ id, topic, at, source, payload }。
- publish：同步、线程安全（跨线程用 call_soon_threadsafe 通知订阅者）。
- subscribe：返回 (queue, 历史快照)，供 SSE 端点做断线重连（Last-Event-ID）。
- 历史保留最近 100 条（断线续传上限）。

★ 单进程内总线，不引入 Redis/Celery（总纲 §1.1 单用户场景足够）。
"""
from __future__ import annotations

import asyncio
import contextlib
import fnmatch
import json
from collections import deque
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from fastapi import Request
from fastapi.responses import StreamingResponse

_BUS_MAXLEN = 100


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class EventBus:
    def __init__(self, maxlen: int = _BUS_MAXLEN) -> None:
        self._history: deque[dict[str, Any]] = deque(maxlen=maxlen)
        self._subscribers: list[asyncio.Queue[dict[str, Any]]] = []
        self._seq = 0
        self._seq_lock = __import__("threading").Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def _next_id(self) -> int:
        with self._seq_lock:
            self._seq += 1
            return self._seq

    def publish(self, topic: str, payload: Any, source: str = "kernel") -> dict[str, Any]:
        """发布事件（同步、线程安全）。返回事件对象。"""
        event = {
            "id": self._next_id(),
            "topic": topic,
            "at": _now_iso(),
            "source": source,
            "payload": payload,
        }
        self._history.append(event)
        if self._subscribers and self._loop is not None:
            for q in list(self._subscribers):
                self._loop.call_soon_threadsafe(q.put_nowait, event)
        return event

    def subscribe(self) -> tuple[asyncio.Queue[dict[str, Any]], list[dict[str, Any]]]:
        """注册订阅者（必须在事件循环内调用）。"""
        self._loop = asyncio.get_running_loop()
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._subscribers.append(q)
        return q, list(self._history)

    def unsubscribe(self, q: asyncio.Queue[dict[str, Any]]) -> None:
        with contextlib.suppress(ValueError):
            self._subscribers.remove(q)

    def sse_response(
        self, request: Request, patterns: list[str] | None = None
    ) -> StreamingResponse:
        """构造 SSE 响应：先看历史补发（Last-Event-ID 续传），再实时推送。"""
        q, history = self.subscribe()
        last = int(request.headers.get("Last-Event-ID") or 0)

        async def generator() -> AsyncIterator[str]:
            try:
                for ev in history:
                    if ev["id"] > last and _match(ev["topic"], patterns or []):
                        yield _format_sse(ev)
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        ev = await asyncio.wait_for(q.get(), timeout=30)
                    except TimeoutError:
                        yield ": keep-alive\n\n"
                        continue
                    if _match(ev["topic"], patterns or []):
                        yield _format_sse(ev)
            finally:
                self.unsubscribe(q)

        return StreamingResponse(
            generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )


def _match(topic: str, patterns: list[str]) -> bool:
    if not patterns:
        return True
    return any(fnmatch.fnmatch(topic, p) for p in patterns)


def _format_sse(event: dict[str, Any]) -> str:
    data = json.dumps(event, ensure_ascii=False, default=str)
    return f"id: {event['id']}\nevent: {event['topic']}\ndata: {data}\n\n"


# 全局单例
event_bus = EventBus()
