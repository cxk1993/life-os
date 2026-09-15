"""Life-OS 后端入口（T03 接管，见 docs/issues/ISSUE-001-api入口归属.md）。

★ 刻意不写"导入失败就回退空壳"的兜底逻辑——那会掩盖 T03 的真实故障，
  属于总纲明令禁止的静默失败。入口保持叫 main:app（tools/task.py 与两份
  docker-compose 都以 main:app 为入口，无需改动它们）。
"""
from __future__ import annotations

from core.app import create_app

app = create_app()
