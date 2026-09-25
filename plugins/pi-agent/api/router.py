"""pi-agent 插件路由 · ★ 第②刀：RPC 适配层接通（对话可用）。

════════════════════════════════════════════════════════════════════
★ 第三方插件结构约束（照 plugins/countdown 的先例，务必遵守）：

  内核按【文件路径】加载第三方路由（core/plugins/discover.py →
  load_python_module_from_file(router_path, f"plugin_thirdparty_{id}_router")），
  模块不属于任何包 → **不能用相对导入**（`from .schema import X` 会抛
  ImportError: attempted relative import with no known parent package）。
  故本文件：出入参模型与服务逻辑**就近写在本文件内**，同目录模块走 `_load_sibling`。

HTTP 契约（全项目统一，不许自创）：
  成功 → 直接返回资源 JSON（200/201），**不包 {code,data}**
  失败 → 抛 core.errors 的 AppError 子类，由内核统一转 RFC7807

★ 降级口径（采纳 workbuddy 拍砖）：
  L1 正常 → 走 pi（有工具能力）
  L2 重启中 → **快速失败**（不排队）
  L3 熔断 → 明确告知「AI 工具能力暂不可用」，**由前端保底轻量对话**

★ 第④刀（会话池）：**一个 session = 一个 pi 子进程**。
  - 外部 agent 用 `session="alpha"` / `"beta"` → **各自独立进程**（互不干扰）
  - `provides` 里三条能力经 **ADR-0003 MCP 桥**自动变成外部可调工具：
      pi_chat_write / pi_session_read / pi_session_write
════════════════════════════════════════════════════════════════════
"""

import importlib.util
import json
import logging
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

log = logging.getLogger("plugin.pi-agent.router")

router = APIRouter()

_PLUGIN_DIR = Path(__file__).resolve().parent.parent
_MANIFEST_PATH = _PLUGIN_DIR / "manifest.json"
with _MANIFEST_PATH.open(encoding="utf-8") as _f:
    _MANIFEST: dict[str, Any] = json.load(_f)


def _load_sibling(name: str):
    """按路径加载同目录模块（第三方插件不能用相对导入）。"""
    mod_name = f"pi_agent_{name}"
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    spec = importlib.util.spec_from_file_location(mod_name, Path(__file__).resolve().parent / f"{name}.py")
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载 {name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _manager():
    """取单会话进程管理器（第②刀形态；health/status 用）。"""
    proc = _load_sibling("process")
    return proc.get_manager(cwd=str(_PLUGIN_DIR / "runtime"))


def _pool():
    """取会话池（第④刀；对话与会话管理走这里）。"""
    sess = _load_sibling("sessions")
    return sess.get_pool(cwd=str(_PLUGIN_DIR / "runtime"))


def _level() -> str:
    """降级层级：池里有活进程 = L1；否则 L2（熔断态由 process 层管，这里给保守值）。"""
    try:
        st = _pool().status()
        return "L1" if st.get("alive", 0) > 0 else "L2"
    except Exception:  # noqa: BLE001
        return "L2"


# ── 出入参 ────────────────────────────────────────────────────


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    # ★ 第④刀：session 名 = 会话锁（同名同进程，异名异进程）
    session_id: str = Field(default="default", max_length=64)


class SessionIn(BaseModel):
    """会话操作（★ 走 POST 而非路径参数 —— MCP 桥的路径是固定的）。"""

    action: str = Field(description="new | lock | release | stats")
    session: str = Field(default="default", max_length=64)


class ChatOut(BaseModel):
    session_id: str
    reply: str
    level: str
    settled: bool
    degraded: bool = False
    detail: str | None = None


# ── 端点 ──────────────────────────────────────────────────────


@router.get("/health")
def health() -> dict[str, Any]:
    """存活探针。ready=子进程是否活着（不主动起进程，避免探针触发拉起）。"""
    try:
        m = _manager()
        st = m.status()
        return {"ok": True, "ready": bool(st.get("alive")), "level": st.get("level")}
    except Exception as exc:  # noqa: BLE001
        return {"ok": True, "ready": False, "level": "L2", "detail": f"{type(exc).__name__}: {exc}"}


@router.get("/manifest")
def manifest() -> dict[str, Any]:
    return _MANIFEST


@router.get("/status")
def status() -> dict[str, Any]:
    """状态快照（UI 顶栏状态点）。"""
    m = _manager()
    st = m.status()
    try:
        st["pool"] = _pool().status()
    except Exception as exc:  # noqa: BLE001
        st["pool"] = {"detail": str(exc)}
    st["id"] = "pi-agent"
    st["stage"] = "rpc+sessions"
    st["level_text"] = {
        "L1": "AI 工具能力可用",
        "L2": "AI 服务启动中，请稍后重试",
        "L3": "AI 工具能力暂不可用（pi 熔断）· 可重试",
    }.get(str(st.get("level")), "未知")
    return st


@router.post("/reset-circuit")
def reset_circuit() -> dict[str, Any]:
    """人工/长周期重试入口：把 L3 熔断解开（对应 UI 上的「重试」）。"""
    m = _manager()
    m.reset_circuit()
    return {"ok": True, "status": m.status()}


@router.post("/chat", response_model=ChatOut)
def chat(body: ChatIn) -> ChatOut:
    """同步版对话（**非流式**，便于测试与简单客户端）。

    ★ L2/L3 不抛 5xx，而是返回 `degraded=True` + 原因 ——
      让前端能优雅降级到「轻量对话」而不是白屏。
    """
    pool = _pool()
    text: list[str] = []
    settled = False
    try:
        for ev in pool.prompt(body.session_id, body.message):
            d = ev.text_delta
            if d:
                text.append(d)
            if ev.is_settled:
                settled = True
                break
    except Exception as exc:  # noqa: BLE001
        log.warning("[pi-agent] chat 降级（session=%s）：%s", body.session_id, exc)
        return ChatOut(
            session_id=body.session_id,
            reply="",
            level=_level(),
            settled=False,
            degraded=True,
            detail=str(exc),
        )
    return ChatOut(
        session_id=body.session_id,
        reply="".join(text),
        level=_level(),
        settled=settled,
    )


# ── 会话管理（★ 第④刀：外部 agent 锁定/切换会话）────────────────


@router.get("/sessions")
def list_sessions() -> dict[str, Any]:
    """★ 列出当前活跃会话（外部 agent 据此发现"谁在用哪个会话"）。

    → 经 MCP 桥暴露为工具 `pi_session_read`。
    """
    pool = _pool()
    return {"sessions": pool.list_sessions(), "pool": pool.status()}


@router.post("/sessions")
def session_action(body: SessionIn) -> dict[str, Any]:
    """★ 会话操作：`new`（新开）/ `lock`（锁定）/ `release`（释放）/ `stats`（统计）。

    → 经 MCP 桥暴露为工具 `pi_session_write`。
    ★ 用 POST + action 而非路径参数 —— MCP 桥的转发路径是固定的，带不了路径变量。
    """
    pool = _pool()
    act = (body.action or "").strip().lower()
    if act == "new":
        return {"action": act, **pool.new_session(body.session)}
    if act == "lock":
        return {"action": act, **pool.lock(body.session)}
    if act == "release":
        return {"action": act, **pool.release(body.session)}
    if act == "stats":
        return {"action": act, **pool.stats(body.session)}
    return {"action": act, "ok": False, "detail": f"未知 action：{act!r}（支持 new|lock|release|stats）"}


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/chat/stream")
def chat_stream(body: ChatIn) -> StreamingResponse:
    """★ 流式对话（SSE）。事件：`delta`（文本增量）/ `settled` / `error`。"""

    def gen() -> Iterator[str]:
        pool = _pool()
        try:
            for ev in pool.prompt(body.session_id, body.message):
                d = ev.text_delta
                if d:
                    yield _sse("delta", {"text": d})
                if ev.is_settled:
                    yield _sse("settled", {"session_id": body.session_id})
                    return
        except Exception as exc:  # noqa: BLE001
            yield _sse("error", {
                "detail": str(exc),
                "level": _level(),
                "degraded": True,
            })

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
