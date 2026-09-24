"""E7 工具接线测试（2026-09-26 hermes）。

覆盖三层：
  ① run_tool_call_loop 机制（假 LLM，无网络）：call → 回填 → 综答 / 拒绝
  ② 白名单与 defs 一致性（第二道闸对表 + V1 只读立场）
  ③ 声明即授权：ai-chat manifest requires ⊇ 工具能力

注：模块目录名带连字符（ai-chat），必须 importlib 动态加载。
"""
from __future__ import annotations

import importlib.util
import json
from datetime import timedelta
from pathlib import Path

_MOD_DIR = Path(__file__).resolve().parents[1] / "modules" / "ai-chat"


def _load(mod_name: str, file_name: str):
    spec = importlib.util.spec_from_file_location(mod_name, _MOD_DIR / file_name)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    # ★ 必须先进 sys.modules 再 exec：@dataclass 解析 __module__ 时要能查到本模块
    import sys

    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


chat_loop = _load("e7_chat_loop_under_test", "chat_loop.py")

ALLOWED_TOOLS = chat_loop.ALLOWED_TOOLS
ChatTurn = chat_loop.ChatTurn
run_tool_call_loop = chat_loop.run_tool_call_loop

# tools.py 依赖 core.deps / fastapi Request —— 仅取纯函数与 defs，导入整包需 app 上下文，
# 故对 defs/window 用同样的动态加载（tools 顶层只 import core.deps，测试环境可加载）。
tools = _load("e7_tools_under_test", "tools.py")
_today_window = tools._today_window
build_tool_defs = tools.build_tool_defs


# ─────────────────────────── ① 循环机制 ───────────────────────────


def test_loop_calls_tool_then_final():
    """假 LLM 第一次要工具、第二次综答 → audit=[call, final]，tool 结果进 turns。"""
    n = {"calls": 0}

    def llm(turns):
        n["calls"] += 1
        if n["calls"] == 1:
            return ChatTurn("assistant", tool_name="dashboard_today_read", tool_args={})
        tool_turn = next(t for t in turns if t.role == "tool")
        assert tool_turn.tool_result["ok"] is True
        return ChatTurn("assistant", text="今天有 2 项日程")

    tools_map = {"dashboard_today_read": lambda a: {"ok": True, "count": 2}}
    s = run_tool_call_loop("今天有什么安排", llm, tools_map)
    assert s.audit == ["call:dashboard_today_read", "final"]
    assert s.turns[-1].text == "今天有 2 项日程"


def test_loop_denies_tool_outside_allowlist():
    """write 类工具不在白名单 → denied，绝不执行。"""
    executed = {"hit": False}

    def w(a):
        executed["hit"] = True
        return {}

    def llm(turns):
        return ChatTurn("assistant", tool_name="todo_item_write", tool_args={"text": "hack"})

    s = run_tool_call_loop("帮我写个待办", llm, {"todo_item_write": w})
    assert s.audit == ["denied:todo_item_write"]
    assert executed["hit"] is False


def test_allowlist_and_defs_consistent():
    """第二道闸对表：build_tool_defs 的名字 ⊆ ALLOWED_TOOLS。"""
    names = {d["function"]["name"] for d in build_tool_defs()}
    assert names <= ALLOWED_TOOLS, f"defs 里有白名单外的工具: {names - ALLOWED_TOOLS}"


def test_no_write_tools_in_allowlist_v1():
    """V1 只读立场钉死：白名单里不许出现 write 工具。"""
    assert not any("write" in t for t in ALLOWED_TOOLS)


def test_max_hops_guard():
    """LLM 永远要工具（死循环模拟）→ max_hops 切断，不无限调。"""

    def llm(turns):
        return ChatTurn("assistant", tool_name="dashboard_today_read", tool_args={})

    tools_map = {"dashboard_today_read": lambda a: {"ok": True}}
    s = run_tool_call_loop("循环吧", llm, tools_map, max_hops=2)
    assert s.audit == ["call:dashboard_today_read", "call:dashboard_today_read", "max_hops"]


# ─────────────────────────── ② 参数窗口 ───────────────────────────


def test_today_window_today_covered():
    """今日窗必须覆盖『现在』：CST 今晨 00:00 = UTC 昨 16:00，换算回来才算对。"""
    from datetime import datetime, timezone

    cst = timezone(timedelta(hours=8))
    w = _today_window()
    start_cst = datetime.fromisoformat(w["from"]).astimezone(cst)
    end_cst = datetime.fromisoformat(w["to"]).astimezone(cst)
    now_cst = datetime.now(cst)
    assert start_cst.hour == 0 and start_cst.minute == 0
    assert start_cst.date() == now_cst.date()          # 窗起点 = CST 今天 00:00
    assert (end_cst - start_cst) == timedelta(days=1)  # 全天窗
    assert start_cst <= now_cst < end_cst              # 现在落在窗内


# ─────────────────────────── ③ 声明即授权 ───────────────────────────


def test_manifest_requires_covers_tool_caps():
    """工具能力必须 ⊆ manifest.requires（get_plugin_client 机器校验的前提）。"""
    manifest = json.loads((_MOD_DIR / "manifest.json").read_text(encoding="utf-8"))
    requires = set(manifest["requires"])
    need = {"calendar.event.read", "todo.item.read", "health.record.read", "dashboard.today.read"}
    assert need <= requires, f"缺声明: {need - requires}"
