"""pi-agent 生命周期钩子 · ★ 第②刀：真启停（带懒启动）。

内核约定（core/plugins/lifecycle.py）：
    api/lifecycle.py 里可定义四个可选钩子，钩子是"尽力而为"：
      - 文件/函数不存在 = 静默跳过（不算错误）
      - 钩子内部抛异常 → 被 manager 捕获写进 plugin_state.last_error，**不许拖垮流程**

★ 启动策略：**懒启动**。
  `on_enable` 只把插件标为 enabled，**不在这里起子进程** ——
  理由：内核启动路径上不该等一个外部进程（起不来会拖慢/拖挂内核启动）。
  真正的拉起发生在**第一次 prompt**（`process.ensure_started()`），
  失败也只是那一次请求降级（L2/L3），**内核与其它插件零影响**。

★ 停止策略：`on_disable` / `on_uninstall` **必须**收干净（进程 + 状态），
  这是 ADR-0002「禁用后系统必须完好」的试金石。
"""

import logging

log = logging.getLogger("plugin.pi-agent")

_STATE: dict[str, object] = {"phase": "disabled"}


def _sessions():
    """延迟导入会话池（第④刀）。"""
    import importlib.util
    import sys
    from pathlib import Path

    name = "pi_agent_sessions"
    if name in sys.modules:
        return sys.modules[name]
    path = Path(__file__).resolve().parent / "sessions.py"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _manager():
    """延迟导入进程管理器（避免插件加载期就碰 subprocess 依赖）。"""
    import importlib.util
    import sys
    from pathlib import Path

    name = "pi_agent_process"
    if name in sys.modules:
        return sys.modules[name]
    path = Path(__file__).resolve().parent / "process.py"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def on_enable(db=None) -> None:
    """插件启用 → 只标记状态（**懒启动**，真进程等第一次请求）。"""
    _STATE["phase"] = "enabled"
    log.info("[pi-agent] on_enable：已启用（pi 子进程将在首次请求时懒启动）")


def on_disable(db=None) -> None:
    """插件禁用 → ★ 收干净所有子进程（禁用后系统必须完好）。"""
    try:
        _sessions().shutdown_pool()      # ★ 会话池（第④刀）
    except Exception as exc:  # noqa: BLE001
        log.warning("[pi-agent] on_disable 收会话池出错（已吞）：%s", exc)
    try:
        _manager().shutdown_manager()    # 单会话管理器（第②刀）
    except Exception as exc:  # noqa: BLE001
        log.warning("[pi-agent] on_disable 收进程时出错（已吞，不拖垮内核）：%s", exc)
    _STATE["phase"] = "disabled"
    log.info("[pi-agent] on_disable：子进程已收，插件已禁用")


def on_uninstall(db=None) -> None:
    """插件卸载 → 停进程 + 清 runtime 状态（不留残留）。"""
    try:
        _sessions().shutdown_pool()
    except Exception as exc:  # noqa: BLE001
        log.warning("[pi-agent] on_uninstall 收会话池出错（已吞）：%s", exc)
    try:
        _manager().shutdown_manager()
    except Exception as exc:  # noqa: BLE001
        log.warning("[pi-agent] on_uninstall 收进程时出错（已吞）：%s", exc)
    _STATE["phase"] = "uninstalled"
    log.info("[pi-agent] on_uninstall：已卸载（runtime 目录保留，便于复装）")
