"""今日摘要聚合 API（U2 · 小日历聚合 · 薄壳）。

★ 总监令61 裁决：U2 端点归属丙案（合并）—— 本模块收敛为薄壳，
  聚合逻辑由内核 BFF（core/app.py）实装，本模块只保留 manifest 壳。

★ 路径遮蔽实录（hermes 实测 2026-09-26）：
  - BFF 端点 = GET /api/v1/summary/today（core/app.py events_router，先挂载）
  - 本模块 /today 挂在同一路径（manifest api.base=/api/v1/summary）
  → FastAPI 先注册先匹配，BFF 独占该路径；本模块 /today 永不触发（死代码）。
  - 旧版转发目标 /bff/agg/today 实测 404（不存在），且若转发到
    /api/v1/summary/today 即自请求（死循环）→ 已删除该转发逻辑。
  → 薄壳只保留 /health；前端一律直调内核 BFF。
"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}