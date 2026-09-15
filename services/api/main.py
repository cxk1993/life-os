"""Life-OS 后端入口（T01 空壳）。

T01 的边界只到这里：**一个能跑起来的 FastAPI 空壳，只有一个 /healthz**。
不含任何业务、不含数据库、不含鉴权 —— 那些分别是 T05–T12 / T04 / T03 的活。

运行：
    python tools/task.py dev            # 与前端一起起（推荐）
    # 或单独起：
    python -m uvicorn main:app --reload --port 8000

★ 归属交接说明（给 T03）：
    `create_app()` 工厂、中间件、异常、日志、鉴权都在 `core/` 下，那是 T03 的领地。
    本文件是 T01 建的空壳入口。请 T03 交付 `core/app.py` 的 `create_app()` 之后，
    把本文件改成两行调用即可（本文件随之归 T03 维护）：

        from core.app import create_app
        app = create_app()

    刻意**没有**写"导入失败就回退到空壳"的兜底逻辑 —— 那会掩盖 T03 的真实故障，
    属于总纲明令禁止的静默失败。
"""
from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(
    title="Life-OS API",
    version="0.1.0",
    description="人生管理系统后端宿主（内核）。本文件目前是 T01 空壳。",
)


@app.get("/healthz", tags=["_kernel"])
def healthz() -> dict[str, bool]:
    """存活探针。docker-compose 的 healthcheck 与 T13 的验收都靠它。"""
    return {"ok": True}
