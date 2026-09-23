"""create_app() 工厂：组装整个后端内核。

★ 入口归属（ISSUE-001）：main.py 只调用本工厂，不做任何兜底回退。
  工厂负责：配置、日志、中间件、异常、路由、模块发现、生命周期。
  不认识任何业务词汇——能力全部由 modules/ 下的插件长出来。
"""
from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
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
from core.manifest import discover_modules
from core.middleware import (
    AccessLogMiddleware,
    IdempotencyMiddleware,
    RateLimitMiddleware,
    TraceIdMiddleware,
)
from core.plugins.activator import PluginActivator
from core.plugins.discover import PluginInfo
from core.plugins.migrations import make_startup_lifespan
from core.registry import ModuleRegistry
from core.security import (
    User,
    create_sse_ticket,
    decode_sse_ticket,
    get_current_user,
)

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

    # ── 模块发现（先于 app 构造：lifespan 需要插件清单）──
    scan_dir = Path(modules_dir) if modules_dir else _DEFAULT_MODULES_DIR
    try:
        discovered = discover_modules(scan_dir)
    except AppError:
        raise  # manifest 校验失败：明确抛出，启动即失败（不许静默跳过）

    # ── 注册表与激活器（先于 app 构造：lifespan 钩子要引用激活器）──
    # TX-ACT-01 注册/激活二分：app.state.modules 是「注册表」（全量清单，
    # /api/v1/modules 由此而来，语义零漂移）；registry.mounted() 是「激活表」
    # （路由真正在跑的）。startup:always（或缺省）启动即激活，event: 型等命中。
    reg = registry or ModuleRegistry()
    activator = PluginActivator(reg)
    # 固化 bound method 引用，add/remove 操作同一对象（去重/摘除都可靠）。
    activator_listener = activator.on_event

    app = FastAPI(
        title="Life-OS API",
        version="0.1.0",
        description="人生管理系统后端宿主（内核）。自动发现并挂载 modules/ 下的插件路由。",
        docs_url="/docs",
        openapi_url="/openapi.json",
        # ISSUE-006：服务真正开始服务前，按台账对账补跑各插件迁移。
        # 测试均不进入 lifespan（TestClient 非 context manager 用法），
        # 故全组测试零感知，生产新库首启即自动建表。
        # TX-ACT-01：对账完成后挂激活器的事件监听、退出时摘除——
        # 迁移对账时点不动（硬约束 3），激活器只搭 lifespan 的顺风车。
        lifespan=make_startup_lifespan(
            [(m.id, d) for m, d in discovered],
            on_started=lambda: event_bus.add_listener(activator_listener),
            on_stopping=lambda: event_bus.remove_listener(activator_listener),
        ),
    )

    reg.bind(app)
    app.state.registry = reg
    app.state.activator = activator
    app.state.modules = {}  # id -> manifest dict（注册表：全量清单）

    # ── 中间件（顺序：CORS 最外，TraceId 最内贴路由）──
    app.add_middleware(IdempotencyMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(TraceIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=settings.cors_allow_credentials,
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
        # TX-ACT-01：modules 仍是「已挂载」（生产口径不变，存量插件零漂移）；
        # 新增 registered/activated/activation_errors 三键暴露注册-激活二分
        # 与激活失败目击（卡档缓行纪律：只报目击，不自动处置）。
        return {
            "ok": True,
            "modules": reg.mounted(),
            "registered": sorted(app.state.modules),
            "activated": activator.activated,
            "activation_errors": activator.last_error,
            "config": settings_as_dict(),
        }

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

    @events_router.post("/events/ticket")
    async def issue_sse_ticket(
        user: Annotated[User, Depends(get_current_user)],
    ) -> dict[str, Any]:
        """签发 SSE 入场券（需 Bearer）。

        ★ F2 加固：浏览器原生 `EventSource` **不能带自定义 header**，SSE 鉴权
          只能走 query；而把 access token 直接塞进 URL 会进浏览器历史 / 代理
          日志 / Referer —— 故用「60 秒 + type=sse」的短时票据代替。前端先用
          已鉴权的 HTTP 请求在本端点换票，再拼到 SSE URL 上。
        """
        return {"ticket": create_sse_ticket(user.sub), "expires_in": 60}

    @events_router.get("/events/subscribe")
    async def subscribe_events(
        # ★ 必须标注为 Request。写成 `Any` 时 FastAPI 认不出这是请求对象，
        #   会把它当成**必填查询参数**，于是不带 ?request=... 就一律 422。
        #   卡片要求的命令是不带参数直接订阅，所以这里不能图省事写 Any。
        request: Request,
        # ★ F2 加固（2026-09-23）：SSE 入场券。**刻意设为可选参数** ——
        #   「端点参数层面无必填查询参数」的既有判据（test_kernel）保持不变，
        #   鉴权失败在函数体内以 401 表达（而不是 FastAPI 的 422）。
        ticket: str | None = Query(
            default=None,
            description="SSE 入场券（先 POST /api/v1/events/ticket 换取，60 秒有效）",
        ),
        topics: str | None = Query(
            default=None,
            description="逗号分隔的 topic 模式，如 order.*,task.*；留空收全部",
        ),
    ) -> StreamingResponse:
        # 无票 / 票据无效 / 过期 / 类型不匹配 → 401（decode_sse_ticket 内部抛）
        decode_sse_ticket(ticket or "")
        patterns = [t.strip() for t in (topics or "").split(",") if t.strip()]
        return event_bus.sse_response(request, patterns)

    app.include_router(events_router, prefix="/api/v1")

    # ── 注册 + 按声明激活 ──
    # TX-ACT-01：注册（app.state.modules 全量登记）与激活（load_router+mount）
    # 二分。缺省 / startup:always 启动即激活（存量 17 插件全走这条，零漂移）；
    # event:<topic> 型只注册登记 pending，事件命中后由激活器延后挂载。
    # 挂载动作统一走 mount_plugin()（前置小步确立的单一入口）。
    for manifest, module_dir in discovered:
        info = PluginInfo(
            id=manifest.id,
            kind=manifest.kind,
            source="builtin",
            manifest=manifest.as_dict(),
            directory=module_dir,
        )
        app.state.modules[manifest.id] = manifest.as_dict()  # 先注册（全量，零漂移）
        if activator.activate_on_startup(info):
            log.info("模块已注册并激活", extra={"module": manifest.id, "base": manifest.api.base})
        else:
            log.info(
                "模块已注册待事件激活",
                extra={"module": manifest.id, "base": manifest.api.base},
            )

    return app
