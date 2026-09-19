"""理财路由（薄：只做参数校验 + 调 service）。

HTTP 契约（全项目统一，不许自创）：
  成功 → 直接返回资源 JSON（200/201）
  失败 → 由内核统一转成 RFC7807 application/problem+json

★ 前缀由内核按 manifest.api.base 自动加，这里**不要写 prefix=**。
★ 路径参数用 Annotated[str, FPath(...)]（不是 = FPath(...)）。
★ 本文件**不要**加 `from __future__ import annotations`：
  它会把 `-> None` 变成字符串 "None" → FastAPI 认为 204 带了响应体 → 整个后端起不来。
★ 204 端点返回注解必须是 `-> None`（无 future import 时安全）。
"""
import json
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from fastapi import Path as FPath
from sqlmodel import Session

from core.deps import get_current_user, get_db
from core.security import User

from .beecount_sync import beecount_source, list_snapshots, sync_snapshot
from .scheduler import scheduler_status, start_scheduler
from .schema import (
    BeeCountSourceOut,
    FinanceEntryCreate,
    FinanceEntryOut,
    FinanceEntryUpdate,
    FinanceListOut,
    FinanceSnapshotListOut,
    FinanceSummaryOut,
    SnapshotSyncOut,
)
from .service import FinanceService

router = APIRouter()

_MANIFEST_PATH = Path(__file__).resolve().parent / "manifest.json"
with _MANIFEST_PATH.open(encoding="utf-8") as _f:
    _MANIFEST = json.load(_f)

# ★ 依赖别名**只做类型**，不要把 Depends 塞进 Annotated。
DbDep = Session
UserDep = User


@router.get("/health")
def health() -> dict[str, bool]:
    """每个插件都必须有 health —— 内核据此判断"该能力是否可用"。"""
    return {"ok": True}


@router.get("/manifest")
def manifest() -> dict:
    """模块清单（前端 / AI 发现能力用）。"""
    return _MANIFEST


@router.get("/entries", response_model=FinanceListOut)
def list_entries(
    category: str | None = Query(None, description="按分类过滤"),
    account: str | None = Query(None, description="按账户过滤"),
    direction: str | None = Query(None, description="expense | income"),
    date_from: str | None = Query(None, description="发生时间下界，带时区 ISO8601"),
    date_to: str | None = Query(None, description="发生时间上界，带时区 ISO8601"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    return FinanceService(db).list_entries(
        category=category,
        account=account,
        direction=direction,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/entries", response_model=FinanceEntryOut, status_code=status.HTTP_201_CREATED
)
def create_entry(
    body: FinanceEntryCreate,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    return FinanceService(db).create(body)


@router.get("/entries/{entry_id}", response_model=FinanceEntryOut)
def get_entry(
    entry_id: Annotated[str, FPath(description="流水 id")],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    return FinanceService(db).get(entry_id)


@router.patch("/entries/{entry_id}", response_model=FinanceEntryOut)
def update_entry(
    entry_id: Annotated[str, FPath(description="流水 id")],
    body: FinanceEntryUpdate,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    return FinanceService(db).update(entry_id, body)


@router.delete("/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(
    entry_id: Annotated[str, FPath(description="流水 id")],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> None:
    FinanceService(db).delete(entry_id)


@router.get("/summary", response_model=FinanceSummaryOut)
def summary(
    date_from: str | None = Query(None, description="区间下界，带时区 ISO8601"),
    date_to: str | None = Query(None, description="区间上界，带时区 ISO8601"),
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> FinanceSummaryOut:
    """区间收支合计 + 按分类合计（固定 schema）。"""
    return FinanceService(db).summary(date_from=date_from, date_to=date_to)


# ───────────────── T08B BeeCount 只读联动 ─────────────────
# 通道：POST {BEECOUNT_BASE_URL}/api/v1/mcp + Bearer PAT（见 beecount_mcp.py）
# 本轮只读：无 delete、无 create_transaction 写路径、禁 /api/v1/sync/*


@router.get("/snapshots", response_model=FinanceSnapshotListOut)
def list_finance_snapshots(
    date_from: str | None = Query(None, description="快照日下界 YYYY-MM-DD"),
    date_to: str | None = Query(None, description="快照日上界 YYYY-MM-DD"),
    limit: int = Query(30, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """每日快照列表（date 倒序）。供 OverviewPanel / 历史曲线。"""
    return list_snapshots(db, date_from=date_from, date_to=date_to, limit=limit, offset=offset)


@router.post("/snapshots/sync", response_model=SnapshotSyncOut)
def sync_finance_snapshots(
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> SnapshotSyncOut:
    """手动触发一次 BeeCount 只读同步（幂等：同日覆盖，不翻倍）。

    对外签名与任务卡 T08 契约一致；实现走 MCP 读工具（v0.2 替换）。
    """
    return sync_snapshot(db)


@router.get("/beecount/source", response_model=BeeCountSourceOut)
def get_beecount_source(
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> BeeCountSourceOut:
    """上游状态：upstream=mock|mcp、是否已配 token、最近同步时间。

    **绝不返回 PAT/token 本身**，只返回 token_present 布尔。
    """
    return beecount_source(db)


@router.get("/snapshots/scheduler")
def get_finance_scheduler_status(
    _user: UserDep = Depends(get_current_user),
) -> dict:
    """A2：定时同步调度状态（enabled / running / last_run）。不暴露密钥。"""
    return scheduler_status()


# A2：模块挂载时尝试启动定时同步。默认 FINANCE_SYNC_ENABLED!=true 时为空操作，
# 测试与未配置环境不会拉起后台线程。
try:
    start_scheduler()
except Exception as _sched_exc:  # noqa: BLE001 — 启动失败不阻断 API 进程
    import logging

    logging.getLogger("finance.scheduler").warning("finance 调度器启动失败: %s", _sched_exc)
