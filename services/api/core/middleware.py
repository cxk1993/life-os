"""内核中间件：trace_id / 访问日志 / 限流 / 幂等。

★ 顺序很重要：trace_id 最先（后续都要用），最后才是路由。
  访问日志只记录方法/路径/状态/耗时，**绝不记录请求体**（防明文密码落盘）。
"""
from __future__ import annotations

import hashlib
import time
import uuid
from collections import defaultdict
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from core.config import get_settings
from core.logging import get_logger, trace_id_var

log = get_logger("kernel.middleware")


class TraceIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Any) -> Response:
        # 优先复用上游传来的 trace_id，否则新生成
        incoming = request.headers.get("X-Trace-Id")
        trace_id = incoming or uuid.uuid4().hex
        request.state.trace_id = trace_id
        token = trace_id_var.set(trace_id)
        try:
            response = await call_next(request)
        finally:
            trace_id_var.reset(token)
        response.headers["X-Trace-Id"] = trace_id
        return response


class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Any) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        # 只记元信息，不记 body
        log.info(
            "access",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "elapsed_ms": round(elapsed_ms, 2),
                "trace_id": getattr(request.state, "trace_id", ""),
            },
        )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """轻量令牌桶：登录 5 次/分，其余 300 次/分（单用户场景足够）。

    跨请求状态用模块级字典 + 锁；重启即清空（开发期可接受）。
    """

    def __init__(self, app: Any) -> None:
        super().__init__(app)
        self._buckets: dict[str, list[float]] = defaultdict(list)
        self._lock = __import__("threading").Lock()

    def _limit_for(self, path: str) -> int:
        s = get_settings()
        if path.startswith("/api/v1/auth/login"):
            return s.rate_limit_login_per_min
        return s.rate_limit_general_per_min

    def _allowed(self, key: str, limit: int, window: float = 60.0) -> bool:
        now = time.time()
        with self._lock:
            hits = self._buckets[key]
            # 清掉窗口外的
            self._buckets[key] = [t for t in hits if now - t < window]
            if len(self._buckets[key]) >= limit:
                return False
            self._buckets[key].append(now)
            return True

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        # 只对 API 路径限流，健康检查/文档不限
        if not request.url.path.startswith("/api/"):
            return await call_next(request)
        limit = self._limit_for(request.url.path)
        # 单用户：以路径为 key（IP 维度在单机上恒为本机，无意义）
        key = request.url.path
        if not self._allowed(key, limit):
            resp = JSONResponse(
                status_code=429,
                content={
                    "type": "about:blank",
                    "title": "Too Many Requests",
                    "status": 429,
                    "detail": f"请求过于频繁，限制 {limit} 次/分钟",
                    "trace_id": getattr(request.state, "trace_id", ""),
                },
            )
            resp.headers["Content-Type"] = "application/problem+json"
            resp.headers["Retry-After"] = "60"
            if getattr(request.state, "trace_id", ""):
                resp.headers["X-Trace-Id"] = request.state.trace_id
            return resp
        return await call_next(request)


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """识别 Idempotency-Key：同 key + 同路径 + 同 body 重复请求直接返回首次结果。

    ★ 缓存 24h；存 SQLite 是 T04 的职责，这里先用内存兜底并留有标记。
    """

    def __init__(self, app: Any) -> None:
        super().__init__(app)
        self._cache: dict[str, tuple[float, int, bytes]] = {}
        self._lock = __import__("threading").Lock()
        self._ttl = get_settings().idempotency_ttl_hours * 3600

    @staticmethod
    def _key(raw_key: str, path: str, body: bytes) -> str:
        digest = hashlib.sha256(body).hexdigest()
        return f"{raw_key}|{path}|{digest}"

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        raw_key = request.headers.get("Idempotency-Key")
        if not raw_key:
            return await call_next(request)
        # 仅对写操作做幂等（读操作天然幂等，不缓存）
        if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
            return await call_next(request)

        body = await request.body()
        key = self._key(raw_key, request.url.path, body)
        now = time.time()
        with self._lock:
            hit = self._cache.get(key)
            if hit and now - hit[0] < self._ttl:
                status, cached = hit[1], hit[2]
                resp = Response(
                    content=cached,
                    status_code=status,
                    media_type="application/json",
                )
                if getattr(request.state, "trace_id", ""):
                    resp.headers["X-Trace-Id"] = request.state.trace_id
                resp.headers["X-Idempotent-Replay"] = "true"
                return resp

        response = await call_next(request)
        # 只缓存成功（2xx）的写操作，失败不缓存（可重试）
        if 200 <= response.status_code < 300:
            try:
                captured = b"".join([chunk async for chunk in response.body_iterator])
            except Exception:  # pragma: no cover - 极端情况不缓存
                return response
            with self._lock:
                self._cache[key] = (now, response.status_code, captured)
            # 重新构造可发送的响应
            new_resp = Response(
                content=captured,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )
            return new_resp
        return response
