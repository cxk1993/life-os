"""pi-agent 骨架自检。

跑法：
    cd services/api && python -m pytest ../../plugins/pi-agent/tests -q

★ 本刀只验证「骨架合规」，不验证 pi 运行时（尚未接入）。
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).resolve().parent.parent


def _load(path: Path, name: str):
    """按文件路径加载模块（★ 第三方插件就是被内核这样加载的，不能相对导入）。"""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def manifest() -> dict:
    return json.loads((PLUGIN_DIR / "manifest.json").read_text(encoding="utf-8"))


# ── manifest 契约 ──────────────────────────────────────────────

def test_id_matches_dirname(manifest):
    """ADR-0002 硬规则：id 等于目录名。"""
    assert manifest["id"] == "pi-agent" == PLUGIN_DIR.name


def test_kind_is_third_party(manifest):
    """★ 关键：必须是 third-party（可禁用可卸载）—— 本方案的立身之本。"""
    assert manifest["kind"] == "third-party"


def test_provides_declared(manifest):
    """本插件对外提供的能力（★ 经 ADR-0003 MCP 桥暴露给外部 AI agent）。

    后为三条（会话池 + 对话）：
      pi.chat.write    → pi_chat_write
      pi.session.read  → pi_session_read
      pi.session.write → pi_session_write
    """
    assert set(manifest["provides"]) == {
        "pi.chat.write", "pi.session.read", "pi.session.write",
    }


def test_api_tools_explicit_mapping(manifest):
    """★ chat 资源要显式映射到 /chat（默认会推导成 /chats）。"""
    assert (manifest.get("api") or {}).get("tools", {}).get("chat") == "/chat"


def test_permissions_are_string_format(manifest):
    """★ 权限用字符串格式（内核 permissions.py 只认这个；对象格式内核未实现）。"""
    perms = manifest["permissions"]
    assert isinstance(perms, list) and all(isinstance(p, str) for p in perms)
    # 收口校验（红线③）
    assert "fs:plugin" in perms
    assert "net:out:localhost" in perms
    # 不许出现通配外网
    assert not any(p in ("net:out:*",) for p in perms)


def test_slots_within_enum(manifest):
    """slots 只能从内核已知的 14 个里挑。"""
    known = {
        "desktop.dock", "desktop.dock-left", "desktop.dock-right", "desktop.widget",
        "dashboard.card", "topbar.action", "calendar.block.renderer", "calendar.overlay",
        "inspector.panel", "settings.page", "search.provider", "ai.tool",
        "notification.channel", "command.palette", "window.sidecar",
    }
    assert set(manifest["slots"]) <= known


def test_lifecycle_hooks_declared(manifest):
    lc = manifest["lifecycle"]
    assert set(lc) == {"onInstall", "onEnable", "onDisable", "onUninstall"}


# ── router ────────────────────────────────────────────────────

def test_router_health():
    """★ 探针语义：ok 恒 True；ready 反映子进程是否活着（**探针不主动拉起**）。

    注意：本测试不断言 ready 的具体值 —— 同进程内若别的测试已把 pi 起起来，
    ready 会是 True（那是正确行为）。要验证"探针不起进程"，见
    test_router_chat.test_health_does_not_spawn（在干净单例下断言 False）。
    """
    mod = _load(PLUGIN_DIR / "api" / "router.py", "pi_agent_router_test")
    h = mod.health()
    assert h["ok"] is True
    assert isinstance(h["ready"], bool)
    assert h["level"] in ("L0", "L1", "L2", "L3")


def test_router_manifest_and_status():
    mod = _load(PLUGIN_DIR / "api" / "router.py", "pi_agent_router_test2")
    assert mod.manifest()["id"] == "pi-agent"
    st = mod.status()
    assert st["stage"] == "rpc+sessions"   # ★ rpc → rpc+sessions
    assert st["level"] in ("L0", "L1", "L2", "L3")  # ★ 四层降级口径（09-28 加 L0 待命）
    assert "level_text" in st


# ── lifecycle（空壳，只验证可调用且不抛）────────────────────────

def test_lifecycle_hooks_callable():
    mod = _load(PLUGIN_DIR / "api" / "lifecycle.py", "pi_agent_lifecycle_test")
    mod.on_enable()
    mod.on_disable()
    mod.on_uninstall()
    assert mod._STATE["phase"] == "uninstalled"
