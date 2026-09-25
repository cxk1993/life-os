"""pi-agent · RPC 适配层（★ TX-FRAME-01 第②刀核心）。

════════════════════════════════════════════════════════════════════
把 pi 作为一个**长驻子进程**托管，用 **JSONL over stdin/stdout** 与它对话。

依据（一手实测 2026-09-25 20:2x）：
  - `pi --mode rpc --no-session --provider life-os --model life-os`
  - 协议：stdin 发 Command，stdout 收 response / session event
  - 事件流：message_update → assistantMessageEvent.text_delta（逐字）
             agent_settled = 「pi 不会再自动继续」（★ 可靠终结信号）
  - 实测响应 5~11s，流式正常

★ 两条实测得来的硬约束（别踩）：
  1. **stdin 不能提前关** —— `printf | pi` 会因 EOF 让 pi 立刻退出（0.3s）；
     必须保持管道打开，读到 agent_settled 再收。
  2. **pi 的 cwd 决定它读哪个 AGENTS.md** —— 生产必须显式指定工作目录
     （否则会读到 Life-OS 之外的工程指令）。

★ 进程托管口径（采纳 workbuddy 拍砖）：
  - 指数退避重启（1/2/4…≤60s）+ 熔断（10 分钟内 ≥5 次 → 停止自动重启）
  - 心跳辨「卡死 vs 崩溃」：进程在但 RPC 超时 = 卡死 → SIGTERM→SIGKILL
  - **三层降级**：L1 正常 / L2 重启中（快速失败，不排队）/ L3 熔断（保底轻量对话）
  - **内核要做的不是让它不崩，而是让它崩了也不影响主人用别的**

★ 第三方插件约束：本文件**不能用相对导入**（内核按路径加载）。
════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("plugin.pi-agent.rpc")

# ── 常量（可被 settings 覆盖）──────────────────────────────────────
DEFAULT_PI_BINARY = "pi"
DEFAULT_PROVIDER = "life-os"
DEFAULT_MODEL = "life-os"
# ★ 思考强度（主人要求 high）。pi 的 `--model` 支持 `:<thinking>` 后缀；
#   实测不加后缀时默认是 medium，故显式带上。
DEFAULT_THINKING = "high"
DEFAULT_MODEL_SPEC = f"{DEFAULT_MODEL}:{DEFAULT_THINKING}"
PROMPT_TIMEOUT_S = 120.0      # 单轮上限（实测 5~11s，留足余量）
HEARTBEAT_TIMEOUT_S = 10.0    # 心跳单次超时
HEARTBEAT_FAILS_TO_KILL = 3   # 连续失败判卡死
BACKOFF_BASE_S = 1.0
BACKOFF_MAX_S = 60.0
CIRCUIT_WINDOW_S = 600.0      # 熔断统计窗（10 分钟）
CIRCUIT_FAILS = 5             # 窗内失败次数上限 → 熔断

# 降级层级
LEVEL_L1 = "L1"  # 正常
LEVEL_L2 = "L2"  # 重启中（快速失败）
LEVEL_L3 = "L3"  # 熔断（保底轻量对话）


class PiRpcError(Exception):
    """RPC 层错误（起不来 / 协议错 / 超时）。"""


@dataclass
class PiEvent:
    """从 pi stdout 解析出的一条记录。"""

    type: str
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def text_delta(self) -> str | None:
        """流式文本增量（message_update → text_delta）。"""
        if self.type != "message_update":
            return None
        ev = self.raw.get("assistantMessageEvent") or {}
        return ev.get("delta") if ev.get("type") == "text_delta" else None

    @property
    def is_settled(self) -> bool:
        """★ 可靠终结信号：pi 不会再自动继续。"""
        return self.type == "agent_settled"


def find_pi_binary(configured: str | None = None) -> str | None:
    """定位 pi 可执行文件。

    顺序：显式配置 → PATH → npm 全局 bin（`~/.npm-global/bin/pi`）。
    ★ 显式配置优先，便于生产指定绝对路径（不依赖 PATH）。
    """
    if configured:
        if os.path.isabs(configured) and os.path.isfile(configured):
            return configured
        found = shutil.which(configured)
        if found:
            return found
        return None
    found = shutil.which(DEFAULT_PI_BINARY)
    if found:
        return found
    # npm 全局 bin 兜底（实测本机 pi 装在这里，不在默认 PATH）
    candidate = os.path.expanduser("~/.npm-global/bin/pi")
    return candidate if os.path.isfile(candidate) else None


class PiRpcClient:
    """对 pi RPC 子进程的瘦客户端（一实例 = 一进程 = 一会话域）。

    用法：
        c = PiRpcClient(cwd="/path/to/workspace")
        c.start()
        for ev in c.prompt("你好"):
            if ev.text_delta: print(ev.text_delta, end="")
            if ev.is_settled: break
        c.stop()
    """

    def __init__(
        self,
        *,
        cwd: str,
        binary: str | None = None,
        provider: str = DEFAULT_PROVIDER,
        model: str = DEFAULT_MODEL_SPEC,
        extra_args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self.cwd = cwd
        self.binary = binary
        self.provider = provider
        self.model = model
        self.extra_args = list(extra_args or [])
        self.env = env
        self._proc: subprocess.Popen[str] | None = None
        self._lock = threading.Lock()
        self._req_seq = 0

    # ── 生命周期 ─────────────────────────────────────────────
    def start(self) -> None:
        """拉起子进程。★ 注意保持 stdin 打开（关掉会让 pi 立即退出）。"""
        if self._proc and self._proc.poll() is None:
            return
        binary = find_pi_binary(self.binary)
        if not binary:
            raise PiRpcError(
                "找不到 pi 可执行文件（请装 `npm i -g @earendil-works/pi-coding-agent@0.87.1` "
                "或在插件设置里指定绝对路径）"
            )
        os.makedirs(self.cwd, exist_ok=True)
        argv = [
            binary, "--mode", "rpc", "--no-session",
            "--provider", self.provider, "--model", self.model,
            *self.extra_args,
        ]
        env = {**os.environ, **(self.env or {})}
        self._proc = subprocess.Popen(  # noqa: S603
            argv,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=self.cwd, env=env, text=True, bufsize=1,
        )
        log.info("[pi-agent] pi 子进程已起 pid=%s cwd=%s", self._proc.pid, self.cwd)

    def is_alive(self) -> bool:
        return bool(self._proc and self._proc.poll() is None)

    def stop(self, *, grace: float = 5.0) -> None:
        """优雅停止：关 stdin（pi 会自行收尾）→ SIGTERM → SIGKILL。"""
        proc = self._proc
        if not proc:
            return
        try:
            if proc.stdin and not proc.stdin.closed:
                proc.stdin.close()
            proc.terminate()
            proc.wait(timeout=grace)
        except Exception:  # noqa: BLE001
            try:
                proc.kill()
            except Exception:  # noqa: BLE001
                pass
        finally:
            self._proc = None
            log.info("[pi-agent] pi 子进程已停")

    # ── 协议收发 ─────────────────────────────────────────────
    def _next_id(self) -> str:
        self._req_seq += 1
        return f"r{self._req_seq}"

    def _send(self, obj: dict[str, Any]) -> None:
        if not self._proc or not self._proc.stdin:
            raise PiRpcError("pi 子进程未启动")
        self._proc.stdin.write(json.dumps(obj, ensure_ascii=False) + "\n")
        self._proc.stdin.flush()

    def _read_event(self, deadline: float) -> PiEvent | None:
        """读一条记录（带 deadline）。返回 None = 超时/进程结束。"""
        proc = self._proc
        if not proc or not proc.stdout:
            return None
        while time.time() < deadline:
            line = proc.stdout.readline()
            if not line:
                return None
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                log.debug("[pi-agent] 非 JSON 行（忽略）：%s", line[:120])
                continue
            return PiEvent(type=str(raw.get("type") or ""), raw=raw)
        return None

    def get_state(self, *, timeout: float = HEARTBEAT_TIMEOUT_S) -> dict[str, Any] | None:
        """心跳：取会话状态。★ 用于辨「卡死 vs 崩溃」（进程在但无响应 = 卡死）。"""
        with self._lock:
            rid = self._next_id()
            try:
                self._send({"id": rid, "type": "get_state"})
            except PiRpcError:
                return None
            deadline = time.time() + timeout
            while True:
                ev = self._read_event(deadline)
                if ev is None:
                    return None
                if ev.type == "response" and ev.raw.get("id") == rid:
                    return ev.raw.get("data") if ev.raw.get("success") else None

    def prompt(self, message: str, *, timeout: float = PROMPT_TIMEOUT_S) -> Iterator[PiEvent]:
        """发一条 prompt，**流式**产出事件直到 agent_settled（或超时）。

        ★ 官方强调：订阅必须在 prompt 之前 —— 本实现先注册读取循环再发，天然满足。
        """
        with self._lock:
            if not self.is_alive():
                raise PiRpcError("pi 子进程不可用（未启动或已退出）")
            rid = self._next_id()
            self._send({"id": rid, "type": "prompt", "message": message})
            deadline = time.time() + timeout
            while True:
                ev = self._read_event(deadline)
                if ev is None:
                    raise PiRpcError(f"pi 响应超时（{timeout:.0f}s）或进程已退出")
                yield ev
                if ev.is_settled:
                    return
