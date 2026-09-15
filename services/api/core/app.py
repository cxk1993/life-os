"""create_app() 工厂：组装整个后端内核。

★ 入口归属（ISSUE-001）：main.py 只调用本工厂，不做任何兜底回退。
  工厂负责：配置、日志、中间件、异常、路由、模块发现、生命周期。
  不认识任何业务词汇——能力全部由 modules/ 下的插件长出来。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, Query
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from core.config import get_settings, settings_as_dict
from core.errors import (
    AppError,
    handle_app_error,
    handle_http_exception,
    handle_unexpected,
    handle_validation_error,
)
from core.events import event_bus
from core.logging import configure_logging, get_logger
from core.manifest import discover_modules, load_router
from core.middleware import (
    AccessLogMiddleware,
    IdempotencyMiddleware,
    RateLimitMiddleware,
    TraceIdMiddleware,
)
from core.registry import ModuleRegistry

log = get_logger("kernel.app")

# 默认模块目录：services/api/modules
_DEFAULT_MODULES_DIR = Path(__file__).resolve().parents[1] / "modules"


def create_app(
    modules_dir: str | Path | None = None,
    registry: ModuleRegistry | None = None,
) -> FastAPI:
    """构建 FastAPI 应用。

    modules_dir：模块扫描目录（测试时可传临时目录）。
    registry：路由挂载表（默认新建一个 ModuleRegistry）。
    """
    settings = get_settings()
    configure_logging(level=settings.log_level, log_dir=settings.log_dir)

    app = FastAPI(
        title="Life-OS API",
        version="0.1.0",
        description="人生管理系统后端宿主（内核）。自动发现并挂载 modules/ 下的插件路由。",
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    reg = registry or ModuleRegistry()
    reg.bind(app)
    app.state.registry = reg
    app.state.modules = {}  # id -> manifest dict

    # ── 中间件（顺序：CORS 最外，TraceId 最内贴路由）──
    app.add_middleware(IdempotencyMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(TraceIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── 异常 -> RFC7807 ──
    app.add_exception_handler(AppError, handle_app_error)
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(Exception, handle_unexpected)

    # ── 存活 / 就绪探针 ──
    @app.get("/healthz", tags=["_kernel"])
    def healthz() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/readyz", tags=["_kernel"])
    def readyz() -> dict[str, Any]:
        return {"ok": True, "modules": reg.mounted(), "config": settings_as_dict()}

    # ── 模块清单（前端 / AI 都靠它发现能力）──
    @app.get("/api/v1/modules", tags=["_kernel"])
    def list_modules() -> dict[str, Any]:
        return {"modules": list(app.state.modules.values()), "count": len(app.state.modules)}

    # ── 聚合 OpenAPI（验收要求出现在 /api/docs）──
    @app.get("/api/docs", tags=["_kernel"], include_in_schema=False)
    def aggregate_docs() -> Any:
        return app.openapi()

    # ── 事件总线 SSE 订阅 ──
    events_router = APIRouter()

    @events_router.get("/events/subscribe")
    async def subscribe_events(
        request: Any,
        topics: str | None = Query(
            default=None,
            description="逗号分隔的 topic 模式，如 calendar.*,todo.*；留空收全部",
        ),
    ) -> Any:
        patterns = [t.strip() for t in (topics or "").split(",") if t.strip()]
        return event_bus.sse_response(request, patterns)

    app.include_router(events_router, prefix="/api/v1")

    # ── 自动发现并挂载模块 ──
    scan_dir = Path(modules_dir) if modules_dir else _DEFAULT_MODULES_DIR
    try:
        discovered = discover_modules(scan_dir)
    except AppError:
        raise  # manifest 校验失败：明确抛出，启动即失败（不许静默跳过）
    for manifest, _dir in discovered:
        router = load_router(manifest.id)
        reg.mount(manifest.id, router, prefix=manifest.api.base)
        app.state.modules[manifest.id] = manifest.as_dict()
        log.info("模块已挂载", extra={"module": manifest.id, "base": manifest.api.base})

    return app
