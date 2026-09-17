"""本机笔记桥（FastAPI，只监听 127.0.0.1）。

★ 唯一入口形态：独立 uvicorn 进程，由 frpc 隧道暴露到云服务器。
★ 暴露端点（内网隧道，仅服务器可访问）：
    GET  /bridge/healthz            存活 + 版本 + 库列表
    GET  /bridge/libs               库配置（md_count）
    GET  /bridge/scan?lib=&limit=    全量索引（流式 ndjson，大库不 OOM）
    GET  /bridge/read?lib=&path=     读全文（content + mtime + hash）
    GET  /bridge/changes?since=      增量变化（供增量索引）
    POST /bridge/write               写回（v0.1 默认 403，mode=rw 才放行）

★ 所有 /bridge/* 请求必须带：X-Bridge-PSK / X-Bridge-Ts / X-Bridge-Nonce / X-Bridge-Sign
★ 绝不监听 0.0.0.0（见 __main__ 与 run.ps1，均写死 127.0.0.1）。
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse

from .config import BridgeConfig, load_config
from .protocol import NONCE_TTL_S, NonceStore, check_timestamp, verify_sig
from .reader import read_note
from .scanner import count_md, scan_lib

log = logging.getLogger("bridge")
logging.basicConfig(level=logging.INFO)

BRIDGE_VERSION = "0.1.0"


def _canonical_path(request: Request) -> str:
    """签名用的路径：path + 规范化查询串（覆盖 GET 查询参数防篡改）。"""
    q = request.url.query
    return request.url.path + (f"?{q}" if q else "")


class BridgeState:
    """桥运行期状态：配置 + nonce 防重放 + 增量变化日志。"""

    def __init__(self, config: BridgeConfig) -> None:
        self.config = config
        self.nonces = NonceStore(ttl=NONCE_TTL_S)
        self._changes: list[dict] = []
        self._seq = 0

    def push_change(self, entry: dict) -> None:
        self._seq += 1
        self._changes.append({"seq": self._seq, **entry})
        if len(self._changes) > 2000:  # 只留最近 2000 条，防内存无限增长
            self._changes = self._changes[-2000:]

    def changes_since(self, since: int) -> list[dict]:
        return [c for c in self._changes if c["seq"] > since]


class BridgeError(Exception):
    status = 400
    title = "Error"

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class Unauthorized(BridgeError):
    status = 401
    title = "Unauthorized"


class NotFound(BridgeError):
    status = 404
    title = "Not Found"


class BadRequest(BridgeError):
    status = 400
    title = "Bad Request"


class Forbidden(BridgeError):
    status = 403
    title = "Forbidden"


def _auth(
    request: Request,
    x_bridge_psk: str | None = Header(default=None, alias="X-Bridge-PSK"),
    x_bridge_ts: str | None = Header(default=None, alias="X-Bridge-Ts"),
    x_bridge_nonce: str | None = Header(default=None, alias="X-Bridge-Nonce"),
    x_bridge_sign: str | None = Header(default=None, alias="X-Bridge-Sign"),
) -> None:
    cfg = request.app.state.bridge.config
    nonces: NonceStore = request.app.state.bridge.nonces
    # ① PSK
    if not x_bridge_psk or x_bridge_psk != cfg.psk:
        log.warning("桥请求被拒：PSK 缺失或错误", extra={"nonce": (x_bridge_nonce or "")[:8]})
        raise Unauthorized("PSK 缺失或错误")
    # ② 时间戳
    try:
        ts = check_timestamp(x_bridge_ts)
    except ValueError as exc:
        raise Unauthorized(str(exc))
    # ③ nonce 重放
    if not x_bridge_nonce:
        raise Unauthorized("缺少 nonce")
    if nonces.seen(x_bridge_nonce):
        raise Unauthorized("nonce 已使用（疑似重放）")
    # ④ 签名
    body = request.scope.get("_bridge_body") or b""
    if not x_bridge_sign or not verify_sig(
        cfg.psk, request.method, _canonical_path(request), ts, x_bridge_nonce, body
    ):
        log.warning("桥请求被拒：签名错误", extra={"nonce": x_bridge_nonce[:8]})
        raise Unauthorized("签名校验失败")
    nonces.add(x_bridge_nonce)


def create_bridge_app(
    config: BridgeConfig | None = None,
    config_path: str | Path | None = None,
) -> FastAPI:
    cfg = config or load_config(config_path or (Path(__file__).resolve().parent / "config.yaml"))
    state = BridgeState(cfg)

    app = FastAPI(title="Life-OS Note Bridge", version=BRIDGE_VERSION)
    app.state.bridge = state

    @app.middleware("http")
    async def _cache_body(request: Request, call_next):
        # 鉴权前把 body 读出来缓存（仅 /bridge/*），供签名校验使用
        if request.url.path.startswith("/bridge/"):
            try:
                request.scope["_bridge_body"] = await request.body()
            except Exception:  # noqa: BLE001
                request.scope["_bridge_body"] = b""
        return await call_next(request)

    @app.get("/healthz")
    def healthz() -> dict:
        return {"ok": True, "service": "bridge"}

    @app.get("/bridge/healthz")
    def bridge_healthz(_: None = Depends(_auth)) -> dict:
        return {
            "ok": True,
            "version": BRIDGE_VERSION,
            "libs": [
                {"id": lib.id, "name": lib.name, "enabled": lib.enabled, "mode": lib.mode}
                for lib in cfg.libs
            ],
        }

    @app.get("/bridge/libs")
    def bridge_libs(_: None = Depends(_auth)) -> dict:
        return {
            "libs": [
                {
                    "id": lib.id,
                    "name": lib.name,
                    "path": lib.path,
                    "mode": lib.mode,
                    "enabled": lib.enabled,
                    "md_count": count_md(lib),
                }
                for lib in cfg.libs
            ]
        }

    @app.get("/bridge/scan")
    def bridge_scan(
        lib: str = Query(...),
        limit: int = Query(5000, ge=1, le=5000),
        _: None = Depends(_auth),
    ) -> StreamingResponse:
        l = cfg.lib(lib)
        if l is None:
            raise NotFound(f"未知库：{lib}")
        if not l.enabled:
            raise NotFound(f"库已禁用：{lib}")
        entries = scan_lib(l, limit=limit)

        def _gen():
            for e in entries:
                yield json.dumps(e, ensure_ascii=False) + "\n"

        return StreamingResponse(
            _gen(),
            media_type="application/x-ndjson",
            headers={"X-Index-Count": str(len(entries))},
        )

    @app.get("/bridge/read")
    def bridge_read(
        lib: str = Query(...),
        path: str = Query(..., alias="path"),
        _: None = Depends(_auth),
    ) -> dict:
        l = cfg.lib(lib)
        if l is None:
            raise NotFound(f"未知库：{lib}")
        if not l.enabled:
            raise NotFound(f"库已禁用：{lib}")
        try:
            note = read_note(l, path)
        except ValueError as exc:  # 路径穿越 / 越界
            raise BadRequest(str(exc))
        except FileNotFoundError as exc:
            raise NotFound(str(exc))
        return note

    @app.get("/bridge/changes")
    def bridge_changes(
        since: int = Query(0, ge=0),
        _: None = Depends(_auth),
    ) -> dict:
        return {"since": since, "changes": state.changes_since(since)}

    @app.post("/bridge/write")
    async def bridge_write(
        request: Request,
        lib: str = Query(...),
        path: str = Query(..., alias="path"),
        _: None = Depends(_auth),
    ) -> dict:
        l = cfg.lib(lib)
        if l is None:
            raise NotFound(f"未知库：{lib}")
        if l.mode != "rw":
            raise Forbidden("该库为只读（mode=ro），写回已禁用")
        body = await request.body()
        target = l.abs_path() / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        log.info("桥写回成功", extra={"lib": lib, "path": path})
        return {"ok": True, "rel_path": path}

    _install_error_handlers(app)
    return app


def _install_error_handlers(app: FastAPI) -> None:
    def _make(exc: BridgeError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status,
            content={
                "type": "about:blank",
                "title": exc.title,
                "status": exc.status,
                "detail": exc.detail,
            },
            headers={"Content-Type": "application/problem+json"},
        )

    for cls in (Unauthorized, NotFound, BadRequest, Forbidden):
        app.add_exception_handler(cls, lambda req, exc, _c=cls: _make(exc))  # type: ignore


if __name__ == "__main__":
    # 只监听本机回环；端口由 run.ps1 / 部署决定（默认 8790，自测用 8791）。
    import os
    import uvicorn

    _app = create_bridge_app(config_path=os.environ.get("BRIDGE_CONFIG") or None)
    uvicorn.run(
        _app,
        host="127.0.0.1",
        port=int(os.environ.get("BRIDGE_PORT", "8790")),
        reload=False,
    )
