"""健康路由（薄：校验 + 调 service）。

★ 前缀由内核按 manifest 加，这里不写 prefix。
★ 本文件不要加 future import；204 端点不要写 -> None 返回注解时注意兼容。
"""
import json
import logging
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi import Path as FPath
from sqlmodel import Session

from core.deps import get_current_user, get_db
from core.security import User

from .module_status import dock_module_status
from .reconcile import reconcile_followups, reconcile_status
from .reconcile_scheduler import scheduler_status as reconcile_scheduler_status
from .reconcile_scheduler import start_scheduler as start_reconcile_scheduler
from .schema import (
    FollowupRequestOut,
    HealthRecordCreate,
    HealthRecordOut,
    HealthRecordUpdate,
    ModulesStatusOut,
    ReconcileOut,
    ReconcileStatusOut,
)
from .service import HealthService

router = APIRouter()

_MANIFEST_PATH = Path(__file__).resolve().parent / "manifest.json"
with _MANIFEST_PATH.open(encoding="utf-8") as _f:
    _MANIFEST = json.load(_f)

DbDep = Session
UserDep = User


@router.get("/health")
def health() -> dict[str, bool]:
    """插件健康探针（恒 200）。"""
    return {"ok": True}


@router.get("/manifest")
def manifest() -> dict:
    """模块清单（前端 / AI 发现能力用）。"""
    return _MANIFEST


@router.get("/records", response_model=list[HealthRecordOut])
def list_records(
    kind: str | None = Query(
        default=None, description="按类型过滤：symptom | medication | appointment | lab（不传=全部）"
    ),
    frm: str | None = Query(default=None, alias="from", description="起始日（YYYY-MM-DD 日历日）"),
    to: str | None = Query(default=None, description="结束日（YYYY-MM-DD 日历日）"),
    followup_only: bool = Query(
        default=False, description="true=只看**需要跟进**的记录（followup_needed=true）"
    ),
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """按条件列健康记录：`kind` 筛类型、`from`/`to` 圈时间区间、`followup_only=true` 只看**待跟进**的。"""
    return HealthService(db).list_records(
        kind=kind, date_from=frm, date_to=to, followup_only=followup_only
    )


@router.get("/records/{record_id}", response_model=HealthRecordOut)
def get_record(
    record_id: Annotated[str, FPath(description="健康记录 id —— 从 GET /records 的结果里取")],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """读单条健康记录。"""
    return HealthService(db).get(record_id)


@router.post("/records", response_model=HealthRecordOut, status_code=status.HTTP_201_CREATED)
def create_record(
    body: HealthRecordCreate,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """记一条健康记录（症状 / 用药 / 复诊 / 体检）。

    ⚠️ `kind` 只认四个值，乱填直接 422；`occurred_at` 必须带时区；
    ⚠️ `followup_due` 是**日历日**（YYYY-MM-DD），不是时刻。
    ⚠️ `followup_needed=true` 会**经事件总线自动联动待办**。
    """
    return HealthService(db).create(body)


@router.patch("/records/{record_id}", response_model=HealthRecordOut)
def update_record(
    record_id: Annotated[str, FPath(description="健康记录 id —— 从 GET /records 的结果里取")],
    body: HealthRecordUpdate,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """改一条健康记录（部分更新）。⚠️ 把 `followup_needed` 由 false 改 true 会**联动建待办**。"""
    return HealthService(db).update(record_id, body)


@router.delete("/records/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_record(
    record_id: Annotated[str, FPath(description="健康记录 id —— 从 GET /records 的结果里取")],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> None:
    """删除一条健康记录（不可恢复）。"""
    HealthService(db).delete(record_id)


@router.post(
    "/records/{record_id}/request-followup",
    response_model=FollowupRequestOut,
)
def request_followup(
    record_id: Annotated[str, FPath(description="健康记录 id —— 从 GET /records 的结果里取")],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """手动再触发跟进事件（只 publish，不 import todo）。"""
    return HealthService(db).request_followup(record_id)


# ── E3 期望态 reconcile（默认只手动；调度 HEAL_RECONCILE_ENABLED）──


@router.post("/followups/reconcile", response_model=ReconcileOut)
def post_reconcile_followups(
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """广播期望态：所有 followup_needed 记录重发 care.requested（消费方幂等收敛）。"""
    return reconcile_followups(db)


@router.get("/followups/reconcile", response_model=ReconcileStatusOut)
def get_reconcile_status(
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """只读期望态规模与调度开关，不 publish。"""
    return reconcile_status(db)


@router.get("/followups/reconcile/scheduler")
def get_reconcile_scheduler(
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """看「跟进核对」定时任务的状态（开没开、上次何时跑）。"""
    return reconcile_scheduler_status()


# ── · 坞模块健康四态（批 A 角 Zcode；只读目击，不自动处置）──


@router.get("/modules", response_model=ModulesStatusOut)
def dock_module_statuses(
    request: Request,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """坞模块四态总览（healthy/degraded/disabled/unknown）+ E3 reconcile 并表。

    结构态判定（进程内注册/激活状态），零网络自探测；census 语义零漂移
    （内核 /api/v1/modules 不动，本端点为 health 前缀下的纯附加）。
    """
    return dock_module_status(request.app, db)


# 模块挂载时尝试启动 reconcile 调度；默认关时为空操作
try:
    _reconcile_sched_started = start_reconcile_scheduler()
except Exception as _reconcile_exc:  # noqa: BLE001
    _reconcile_sched_started = False
    logging.getLogger("health.router").warning(
        "health reconcile 调度器启动失败: %s", _reconcile_exc
    )
