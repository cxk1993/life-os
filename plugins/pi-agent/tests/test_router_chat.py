"""pi-agent router 对话端点测试。

★ 全部**离线**：不真起 pi，验证的是「降级行为正确」——
   熔断/起不来时必须**优雅降级**（返回 degraded=True + 原因），
   而不是抛 5xx 让前端白屏。这是 workbuddy 拍砖里最重要的一条。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).resolve().parent.parent
API_DIR = PLUGIN_DIR / "api"


def _load(name: str):
    mod_name = f"pi_agent_rt_{name}"
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    spec = importlib.util.spec_from_file_location(mod_name, API_DIR / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def router_mod():
    """加载 router，并在**每个测试前后重置单例**（避免状态污染）。

    ★ 教训：单例是全局的，测试之间会串（第一次跑时前一个测试真的把 pi 起了起来，
      后一个测试就拿到 L1 而不是预期的降级态）。
    ★ 2026-09-28 补充：连 `_ever_started` 标记也要重置 —— 否则跑过
      "尝试启动"用例后，后续"从未启动"用例会拿到被污染的 True。
    """
    mod = _load("router")
    proc = _load("process")
    proc.shutdown_manager()
    # ★ 池单例同样要清标记（它不是 fixture 管的）
    try:
        pool = mod._pool()
        pool.stop_all()
        pool._ever_started = False
        pool._last_error = None
    except Exception:  # noqa: BLE001
        pass
    yield mod
    proc.shutdown_manager()
    try:
        pool = mod._pool()
        pool.stop_all()
        pool._ever_started = False
        pool._last_error = None
    except Exception:  # noqa: BLE001
        pass


# ── 端点存在性与形状 ────────────────────────────────────────────

def test_status_shape(router_mod):
    st = router_mod.status()
    for k in ("id", "stage", "level", "level_text", "alive", "model", "provider"):
        assert k in st, f"status 缺字段 {k}"
    assert st["id"] == "pi-agent"
    assert st["stage"] == "rpc+sessions"   # ★ 
    assert "pool" in st                     # ★ 会话池状态


def test_health_does_not_spawn(router_mod):
    """★ 探针不许触发拉起（否则健康检查会把进程带起来）。"""
    h = router_mod.health()
    assert h["ok"] is True
    assert h["ready"] is False


def test_manifest_endpoint(router_mod):
    assert router_mod.manifest()["id"] == "pi-agent"


# ── ★ 降级行为（核心）──────────────────────────────────────────

def test_chat_degrades_when_pi_unavailable(router_mod):
    """pi 起不来 → **不抛异常**，而是 degraded=True + detail。

    做法：把**单例**的 binary 改成不存在的路径（router 用的就是这个单例）。
    """
    # ★ 后 /chat 走**会话池**：把池的 binary 钉死为不存在
    pool = router_mod._pool()
    pool.stop_all()
    pool._binary = "/nonexistent/pi-xyz"

    out = router_mod.chat(router_mod.ChatIn(message="你好"))
    assert out.degraded is True, f"应降级，实际：{out}"
    assert out.reply == ""
    assert out.detail  # 必须给出原因，不许静默
    assert out.level in ("L2", "L3")


def test_chat_degrades_when_circuit_open(router_mod):
    """★ 熔断（L3）时同样优雅降级，且 detail 明确说明是熔断。"""
    pool = router_mod._pool()
    pool.stop_all()
    pool._binary = "/nonexistent/pi-xyz"

    out = router_mod.chat(router_mod.ChatIn(message="你好"))
    assert out.degraded is True, f"应降级，实际：{out}"
    assert out.detail  # 必须给出原因


def test_reset_circuit_endpoint(router_mod):
    proc = _load("process")
    m = router_mod._manager()           # 熔断是 process 层概念，仍用它测
    m.stop()
    m._binary = "/nonexistent/pi-xyz"
    for _ in range(proc.CIRCUIT_FAILS):
        m._note_failure()
    assert m.status()["circuit_open"] is True

    res = router_mod.reset_circuit()
    assert res["ok"] is True
    assert res["status"]["circuit_open"] is False


def test_chat_input_validation(router_mod):
    """空消息被 pydantic 挡下（min_length=1）。"""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        router_mod.ChatIn(message="")


# ── ★ 会话端点 ──────────────────────────────────────────

def test_sessions_list_shape(router_mod):
    d = router_mod.list_sessions()
    assert "sessions" in d and "pool" in d
    assert isinstance(d["sessions"], list)


def test_session_action_unknown(router_mod):
    r = router_mod.session_action(router_mod.SessionIn(action="nope"))
    assert r["ok"] is False and "未知 action" in r["detail"]


def test_session_action_release_missing(router_mod):
    r = router_mod.session_action(router_mod.SessionIn(action="release", session="nobody"))
    assert r["released"] is False


def test_session_stats_missing_session(router_mod):
    r = router_mod.session_action(router_mod.SessionIn(action="stats", session="nobody"))
    assert r["exists"] is False


def test_pool_status_shape(router_mod):
    st = router_mod._pool().status()
    for k in ("sessions", "max_sessions", "busy", "alive", "names"):
        assert k in st


# ── ★ 2026-09-28（方案 A · 主人候办③「状态点恒显启动中」）回归 ──────

def test_level_is_l0_when_never_started(router_mod):
    """★ 回归：**从未启动过**（懒启动待命）→ level = L0，**不再报 L2「启动中」**。

    这是本轮修复的核心判据。修复前 `_level()` 只看单会话管理器，
    从没聊过天 ⇒ 恒报 L2「启动中」，pi 明明健康可用也一直显示"启动中"。
    """
    pool = router_mod._pool()
    pool.stop_all()
    # 模拟"从未启动"：清掉两处标记
    pool._ever_started = False
    m = router_mod._manager()
    m._client = None
    m._ever_started = False
    m._circuit_open = False

    st = router_mod.status()
    assert st["level"] == "L0", f"应报 L0 待命，实际 {st['level']}"
    assert "待命" in st["level_text"]


def test_level_is_l2_after_start_attempt_failed(router_mod):
    """★ 回归：**尝试过**启动但失败 → level = L2（真·异常），与 L0 区分开。"""
    pool = router_mod._pool()
    pool.stop_all()
    pool._binary = "/nonexistent/pi-xyz"
    m = router_mod._manager()
    m._client = None
    m._circuit_open = False

    # 发一条消息 → 池真尝试建会话（必失败）
    out = router_mod.chat(router_mod.ChatIn(message="你好"))
    assert out.degraded is True

    st = router_mod.status()
    assert st["level"] == "L2", f"试过失败应报 L2，实际 {st['level']}"
    assert "启动失败" in st["level_text"]


# ── SSE 形状（离线：只验证事件编码格式）─────────────────────────

def test_sse_encoding():
    mod = _load("router")
    s = mod._sse("delta", {"text": "你"})
    assert s.startswith("event: delta\n")
    assert s.endswith("\n\n")
    assert '"你"' in s  # 中文不转义
