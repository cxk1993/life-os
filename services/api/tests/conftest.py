"""测试会话级保险：清理可能残留的临时模块目录。

## 为什么需要这个文件

`test_kernel.py` 里的 `probe_module` fixture 必须把临时模块造在**真实的** `modules/` 之下
（因为 `load_router` 是按模块 id 从 `modules` 包里 import 的，放临时目录 import 不到），
所以它有污染仓库的可能。

它自己带 `finally` 清理。但有一个 `finally` 兜不住的情况：**pytest 进程被强杀**
（编排者中途停掉任务、进程被 SIGKILL），teardown 根本不执行 —— 于是仓库里留下了
`modules/t03probe/`。这个坑**在 T03 验收时实际踩过一次**，排查了半天才确认是残留。

所以这里再加一层会话级保险：会话开始前清一次、结束后再清一次。
即使上一轮是被强杀的，下一轮跑测试时也会自动收拾干净。
"""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest

MODULES_DIR = Path(__file__).resolve().parents[1] / "modules"
PLUGINS_DIR = Path(__file__).resolve().parents[3] / "plugins"   # 项目根/plugins
DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# 测试专用的临时模块名（集中登记，便于一眼看出哪些是"不是真模块"的东西）
LEFTOVER_PROBE_MODULES = ("t03probe",)

# 测试专用的第三方插件目录前缀（T14 的插件测试会往 plugins/ 下造真插件，正常由
# uninstall 删掉；但进程被强杀时 teardown 不执行，就会像下面这样留下来）
LEFTOVER_PLUGIN_GLOBS = ("demo3p-*", "drillplug")


def _clean_leftovers() -> None:
    for name in LEFTOVER_PROBE_MODULES:
        d = MODULES_DIR / name
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
    for pattern in LEFTOVER_PLUGIN_GLOBS:
        for d in PLUGINS_DIR.glob(pattern):
            if d.is_dir():
                shutil.rmtree(d, ignore_errors=True)


def _clean_tmp_dbs() -> None:
    """清掉 tmp_*.db 测试库残留。

    T15/T17 等卡用 data/tmp_*.db 做隔离库；进程被强杀或跨次运行残留时，
    库里的旧数据会让全量运行出现偶发断言失败（2026-09-19 实测一例：
    test_restore_revision_keeps_history 因残留状态偶发红一次）。
    会话开始前清一次，测试自己会在 fixture 里重建表。
    """
    for p in DATA_DIR.glob("tmp_*.db"):
        p.unlink(missing_ok=True)


@pytest.fixture(scope="session", autouse=True)
def _clean_leftover_probe_modules() -> Iterator[None]:
    _clean_leftovers()
    _clean_tmp_dbs()
    yield
    _clean_leftovers()
