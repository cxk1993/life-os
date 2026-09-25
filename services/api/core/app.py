"""create_app() 工厂：组装整个后端内核。

★ 入口归属（ISSUE-001）：main.py 只调用本工厂，不做任何兜底回退。
  工厂负责：配置、日志、中间件、异常、路由、模块发现、生命周期。
  不认识任何业务词汇——能力全部由 modules/ 下的插件长出来。
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Annotated, Any

import httpx
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
    get_optional_user,
)

log = get_logger("kernel.app")


async def _fetch_one(
    client: httpx.AsyncClient,
    pid: str,
    url: str,
    headers: dict[str, str],
    timeout: float,
) -> dict[str, Any]:
    """转发一家插件的 today-summary（模块级，便于用 httpx.MockTransport 单测注入）。

    状态语义：404 = not-implemented（合法）· 5xx/网络错 = unavailable · 200 = ok（data 原样透传）。
    ★ R-1（令 57）：这里**不解析** data 的业务字段，只包装状态 —— 内核只许转发，不许解释。
    """
    try:
        r = await client.get(url, headers=headers, timeout=timeout)
    except Exception:  # noqa: BLE001 — 网络/超时一律 unavailable（缺一不塌）
        return {"id": pid, "status": "unavailable"}
    if r.status_code == 404:
        return {"id": pid, "status": "not-implemented"}
    if r.status_code >= 500:
        return {"id": pid, "status": "unavailable"}
    if r.status_code == 200:
        try:
            return {"id": pid, "status": "ok", "data": r.json()}
        except ValueError:
            return {"id": pid, "status": "unavailable"}
    return {"id": pid, "status": "unavailable"}

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
    # ISSUE-011 案 C（总监令52 裁1）：裸调只回「能点亮图标」的最小字段
    # （id/name/icon/version），持有效 token 才回全量能力地图；
    # 令牌无效/过期仍 401（与 /api/v1/plugins 口径对齐，避免假 token 反而少信息）。
    _PUBLIC_MODULE_FIELDS = ("id", "name", "icon", "version")

    @app.get("/api/v1/modules", tags=["_kernel"])
    def list_modules(
        user: User | None = Depends(get_optional_user),  # noqa: B008
    ) -> dict[str, Any]:
        modules = list(app.state.modules.values())
        if user is not None:
            return {
                "modules": modules,
                "count": len(modules),
                "visibility": "full",
            }
        public = [
            {k: (m.get(k) if isinstance(m, dict) else None) for k in _PUBLIC_MODULE_FIELDS}
            for m in modules
        ]
        return {"modules": public, "count": len(public), "visibility": "public"}

    # ── 聚合 OpenAPI（验收要求出现在 /api/docs）──
    # ★ 乙案（总监令 92/95 · 2026-09-25）：内核挂载模块时统一提供 openapi 端点
    #   —— 23 模块 manifest 均声明 api.openapi 但零实现、零消费（模板惯例字段）；
    #   内核兜底让声明成真，未来新模块自动受益。
    @app.get("/api/docs", tags=["_kernel"], include_in_schema=False)
    def aggregate_docs() -> Any:
        return app.openapi()

    @app.get("/api/{module_id}/openapi.json", tags=["_kernel"], include_in_schema=False)
    def module_openapi(module_id: str, request: Request) -> Any:
        """模块级 openapi 端点（内核兜底）—— 按 manifest 声明路径返回该模块的 schema。"""
        if module_id not in app.state.modules:
            raise HTTPException(status_code=404, detail=f"模块 {module_id} 未注册")
        mod = app.state.modules[module_id]
        base = mod.get("api", {}).get("base")
        if not base:
            raise HTTPException(status_code=404, detail=f"模块 {module_id} 未声明 api.base")
        # 从全局 schema 中提取该模块的路径前缀
        full = app.openapi()
        paths = {
            p: v
            for p, v in full.get("paths", {}).items()
            if p.startswith(base)
        }
        return {**full, "paths": paths}

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
        decode_sse_ticket(ticket or "")
        patterns = [t.strip() for t in (topics or "").split(",") if t.strip()]
        return event_bus.sse_response(request, patterns)

    # ── U2 聚合端点（TX-AGG-01 端点层 · BFF 代理，2026-09-24）────────────
    # ★ 红线 R-1（总监令 57 采纳 astrbot 安全审查）：内核**只许转发，不许解释** ——
    #   本端点不解析 / 不合并任何插件业务语义，只做「带调用者凭证的 HTTP 转发」+ 状态包装。
    # 判据：S-1 转发目标由内核注册表决定（防 SSRF，不得由请求参数决定）
    #       S-2 token 只透传给插件自有端点、不落日志不进 URL + 单家超时（防 hang 放大）
    #       S-3 审计只记操作与状态，不含 Authorization
    # ★ 鉴权：聚合的是用户数据，端点本身必须先过 get_current_user（不能成为新的裸奔口）。
    # ★ 自查修正（2026-09-24 深夜 · 主人「严格检验」轮）：原硬编码四家违反
    #   「一切皆插件」ADR-0003 —— 新插件加聚合源要改内核代码。
    #   改为**从 manifest 动态发现**：插件在 provides 声明 x.summary.today
    #   即自动成为聚合源，零内核改动（Manifest 模型 D′ 后字段可见）。
    _summary_providers: tuple[tuple[str, str], ...] = tuple(
        (m.id, f"/api/v1/{m.id}/today-summary")
        for m, _ in discovered
        if "x.summary.today" in (m.provides or ())
    )
    _SUMMARY_TIMEOUT = 3.0  # ★ S-2：单家超时（秒）

    @events_router.get("/summary/today")
    async def summary_today(
        request: Request,
        user: Annotated[User, Depends(get_current_user)],  # ★ 聚合的是用户数据，必须鉴权
    ) -> dict[str, Any]:
        import httpx

        auth = request.headers.get("authorization")
        headers = {"Authorization": auth} if auth else {}
        # ★ 自环走**本机回环**，不绕外网域名（汐瑶 11:47 坐实的 BFF 缺陷根因）：
        #   若用 request.url（生产 = https://life...:8443），聚合转发会出公网 DNS + nginx
        #   再绕回 uvicorn —— 实测超时（3s）→ 四家全 unavailable，而四源直调明明 200。
        #   内核调自己 = 127.0.0.1:18000 一跳直达。端口可由 LIFE_SUMMARY_INTERNAL_PORT 覆盖。
        port = os.environ.get("LIFE_SUMMARY_INTERNAL_PORT", "18000")
        base = f"http://127.0.0.1:{port}"
        async with httpx.AsyncClient() as client:
            providers = list(
                await asyncio.gather(
                    *(
                        _fetch_one(
                            client, pid, base + path, headers, _SUMMARY_TIMEOUT
                        )
                        for pid, path in _summary_providers
                    )
                )
            )
        # ★ S-3：审计只记「谁、什么状态」，绝不含 Authorization / 业务内容
        log.info(
            "summary.today 聚合完成",
            extra={"providers": {p["id"]: p["status"] for p in providers}},
        )
        return {"providers": providers}


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
