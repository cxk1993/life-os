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

from fastapi import APIRouter, Request, Depends, Query, status
from fastapi import Path as FPath
from sqlmodel import Session

from core.deps import get_current_user, get_db, get_plugin_client
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
    """每个插件都必须有 health —— 内核据此判断「该能力是否可用」。（恒 200）"""
    return {"ok": True}


@router.get("/manifest")
def manifest() -> dict:
    """模块清单（前端 / AI 发现能力用）。"""
    return _MANIFEST


# ───────────────────────── agents ─────────────────────────
@router.get("/agents", response_model=list[AgentOut])
def list_agents(
    enabled_only: bool = Query(
        False, description="true=只列**已启用**的 agent（默认列出全部，含停用的）"
    ),
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """列出已登记的 agent —— 就是「能接活的执行体」清单（名字 / 能力 / 负载 / 是否启用）。"""
    return AgentsService(db).list_agents(enabled_only)


@router.post("/agents", response_model=AgentOut, status_code=status.HTTP_201_CREATED)
def create_agent(
    body: AgentCreate,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """登记一个 agent（能力清单写进 `capabilities`，派发时按它匹配）。"""
    return AgentsService(db).create_agent(body)


@router.get("/agents/{agent_id}", response_model=AgentOut)
def get_agent(
    agent_id: Annotated[str, FPath()],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """读单个 agent 详情。"""
    return AgentsService(db).get_agent(agent_id)


@router.patch("/agents/{agent_id}", response_model=AgentOut)
def update_agent(
    agent_id: Annotated[str, FPath()],
    body: AgentUpdate,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """改 agent（名字 / 描述 / 能力 / 回调地址 / 启用 / 负载）。
    ⚠️ `capabilities` 是**整组替换**，不是追加。"""
    return AgentsService(db).update_agent(agent_id, body)


@router.delete("/agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent(
    agent_id: Annotated[str, FPath()],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> None:
    """注销一个 agent（**不影响它已承接的历史任务**）。"""
    AgentsService(db).delete_agent(agent_id)


# ───────────────────────── tasks ─────────────────────────
@router.get("/tasks", response_model=list[TaskOut])
def list_tasks(
    status_filter: str | None = Query(
        None,
        alias="status",
        description="按状态过滤：draft | queued | running | done | failed | cancelled；不传=全部",
    ),
    assignee: str | None = Query(
        None, description="按**承接者名字**过滤（存的是 agent 的 name，不是 id）"
    ),
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """列出任务块（编排的核心读口）。`assignee` 存的是 agent **名字**，不是 id。"""
    return AgentsService(db).list_tasks(status=status_filter, assignee=assignee)


@router.post("/tasks", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(
    body: TaskCreate,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """新建一个任务块（默认落在 `draft`）。要立刻派发，请再调 `POST /tasks/{id}/execute`。"""
    return AgentsService(db).create_task(body)


@router.get("/tasks/{task_id}", response_model=TaskOut)
def get_task(
    task_id: Annotated[str, FPath()],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """读单个任务块（含 `result` / 派发记录 / 当前状态）。"""
    return AgentsService(db).get_task(task_id)


@router.patch("/tasks/{task_id}", response_model=TaskOut)
def update_task(
    task_id: Annotated[str, FPath()],
    body: TaskUpdate,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """改任务块（含**手工推进 `status`**）。
    ⚠️ 迁移受状态机约束：draft→queued/cancelled · queued→running/done/failed/cancelled ·
    running→done/failed/cancelled · failed→queued。"""
    return AgentsService(db).update_task(task_id, body)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: Annotated[str, FPath()],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> None:
    """删除一个任务块（**连带其派发记录**，不可恢复）。"""
    AgentsService(db).delete_task(task_id)


@router.post("/tasks/{task_id}/dispatch", response_model=DispatchOut)
def dispatch_task(
    task_id: Annotated[str, FPath()],
    body: DispatchIn,
    request: Request,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """派发任务块。

    ★ 2026-09-25 TX-FRAME-01 第⑥刀：
      - `mode="pi"` → **真执行**：经 `pi.chat.write` 能力调内嵌 Pi（任务块独立会话），
        结果写回 `task.result` 并推进状态机；
      - 其余模式（webhook/poll/mcp）**保持原语义**（只记账 + 推进状态机，不调外网）。

    ★ 跨插件调用只走 API（ADR-0002 禁止 import）；能力声明在 manifest.requires，
      `get_plugin_client` 机器校验 ⊆ requires（越权 403）。
    """
    pi_client = None
    if body.mode == "pi":
        pi_client = get_plugin_client(request, ["pi.chat.write"])
    return AgentsService(db).dispatch(task_id, body, pi_client=pi_client)


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
    """编排概览：任务各状态计数 + agent 总数/启用数（dashboard 卡片用）。"""
    return AgentsService(db).summary()
