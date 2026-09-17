"""插件路由：AI 编排。

HTTP 契约（全项目统一，不许自创）：
  成功 → 直接返回资源 JSON（200/201）
  失败 → 由内核统一转成 RFC7807 application/problem+json

★ 前缀由内核按 manifest.api.base 自动加，这里不要写 prefix=。
★ 路径参数用 Annotated[str, FPath()]；body 必填不写 = None。
★ 204 端点写 `-> None`（本文件不要加 future import）。
★ 模块之间用包路径导入（from modules.agents.xxx import ...）。
"""
import json
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from fastapi import Path as FPath
from sqlmodel import Session

from core.deps import get_current_user, get_db
from core.security import User

from .schema import (
    AgentCreate,
    AgentOut,
    AgentUpdate,
    DispatchIn,
    DispatchOut,
    ReportIn,
    SummaryOut,
    TaskCreate,
    TaskOut,
    TaskUpdate,
)
from .service import AgentsService

router = APIRouter()

_MANIFEST_PATH = Path(__file__).resolve().parent / "manifest.json"
with _MANIFEST_PATH.open(encoding="utf-8") as _f:
    _MANIFEST = json.load(_f)

# ★ 依赖别名只做类型，不要把 Depends 塞进 Annotated。
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


# ───────────────────────── agents ─────────────────────────
@router.get("/agents", response_model=list[AgentOut])
def list_agents(
    enabled_only: bool = Query(False),
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> list[dict[str, Any]]:
    return AgentsService(db).list_agents(enabled_only)


@router.post("/agents", response_model=AgentOut, status_code=status.HTTP_201_CREATED)
def create_agent(
    body: AgentCreate,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    return AgentsService(db).create_agent(body)


@router.get("/agents/{agent_id}", response_model=AgentOut)
def get_agent(
    agent_id: Annotated[str, FPath()],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    return AgentsService(db).get_agent(agent_id)


@router.patch("/agents/{agent_id}", response_model=AgentOut)
def update_agent(
    agent_id: Annotated[str, FPath()],
    body: AgentUpdate,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    return AgentsService(db).update_agent(agent_id, body)


@router.delete("/agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent(
    agent_id: Annotated[str, FPath()],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> None:
    AgentsService(db).delete_agent(agent_id)


# ───────────────────────── tasks ─────────────────────────
@router.get("/tasks", response_model=list[TaskOut])
def list_tasks(
    status_filter: str | None = Query(None, alias="status"),
    assignee: str | None = Query(None),
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> list[dict[str, Any]]:
    return AgentsService(db).list_tasks(status=status_filter, assignee=assignee)


@router.post("/tasks", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(
    body: TaskCreate,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    return AgentsService(db).create_task(body)


@router.get("/tasks/{task_id}", response_model=TaskOut)
def get_task(
    task_id: Annotated[str, FPath()],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    return AgentsService(db).get_task(task_id)


@router.patch("/tasks/{task_id}", response_model=TaskOut)
def update_task(
    task_id: Annotated[str, FPath()],
    body: TaskUpdate,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    return AgentsService(db).update_task(task_id, body)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: Annotated[str, FPath()],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> None:
    AgentsService(db).delete_task(task_id)


@router.post("/tasks/{task_id}/dispatch", response_model=DispatchOut)
def dispatch_task(
    task_id: Annotated[str, FPath()],
    body: DispatchIn,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """离线派发：只记账 + 推进状态机，不调外网。"""
    return AgentsService(db).dispatch(task_id, body)


@router.post("/tasks/{task_id}/report", response_model=TaskOut)
def report_task(
    task_id: Annotated[str, FPath()],
    body: ReportIn,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """子 agent 回报结果（v0.1 由调用方写入，不依赖外部 AI API）。"""
    return AgentsService(db).report(task_id, body)


@router.get("/summary", response_model=SummaryOut)
def summary(
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> SummaryOut:
    return AgentsService(db).summary()
