"""AI 编排业务逻辑：agent 注册 CRUD + 任务块 CRUD + 离线派发/回报 + 概览。

★ v0.1 不真调外网：dispatch 只写 AgentDispatch 记账 + 状态机推进；
  report 由调用方直接写结果。外部 AI client 抽象留给后续版本。
★ 状态机：draft → queued → running → (done | failed | cancelled)；
  done 不可再改；failed 可重试回 queued。
★ 可空列比较用 sqlmodel.col()。
★ 事件在本层 publish，内核 SSE 自动下推。
"""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlmodel import Session, col, select

from core.errors import NotFoundError, ValidationError
from core.events import event_bus
from db.base import utcnow

from .models import DISPATCH_MODE, TASK_STATUS, AgentAgent, AgentDispatch, AgentTask
from .schema import (
    AgentCreate,
    AgentUpdate,
    DispatchIn,
    ReportIn,
    SummaryOut,
    TaskCreate,
    TaskUpdate,
)

# 状态机：from → 允许转入的 to
# v0.1 离线派发不真正跑 runner，允许 queued 直接回报终态（done/failed/cancelled）。
_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"queued", "cancelled"},
    "queued": {"running", "done", "failed", "cancelled"},
    "running": {"done", "failed", "cancelled"},
    "failed": {"queued"},
    "done": set(),
    "cancelled": set(),
}

# 派发允许的源状态
_DISPATCHABLE = {"draft", "queued", "failed"}


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return list(value) if hasattr(value, "__iter__") else [value]


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    return dict(value)


class AgentsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ───────────────────────── 序列化 ─────────────────────────
    def _dump_agent(self, a: AgentAgent) -> dict[str, Any]:
        return {
            "id": a.id,
            "name": a.name,
            "description": a.description or "",
            "capabilities": _as_list(a.capabilities),
            "load": a.load,
            "enabled": bool(a.enabled),
            "callback_url": a.callback_url,
            "last_seen": a.last_seen,
            "created_at": a.created_at,
            "updated_at": a.updated_at,
        }

    def _dump_task(self, t: AgentTask) -> dict[str, Any]:
        return {
            "id": t.id,
            "title": t.title,
            "description": t.description or "",
            "status": t.status,
            "assignee": t.assignee,
            "priority": t.priority,
            "inputs": _as_list(t.inputs),
            "outputs": _as_list(t.outputs),
            "acceptance": _as_list(t.acceptance),
            "constraints": _as_list(t.constraints),
            "payload": _as_dict(t.payload),
            "result": t.result,
            "result_status": t.result_status,
            "mode": t.mode,
            "callback_url": t.callback_url,
            "dispatch_id": t.dispatch_id,
            "started_at": t.started_at,
            "finished_at": t.finished_at,
            "attempts": t.attempts,
            "trace_id": t.trace_id,
            "source": t.source,
            "created_at": t.created_at,
            "updated_at": t.updated_at,
        }

    def _dump_dispatch(self, d: AgentDispatch, task: AgentTask) -> dict[str, Any]:
        return {
            "id": d.id,
            "task_id": d.task_id,
            "dispatch_id": d.dispatch_id,
            "mode": d.mode,
            "target": d.target,
            "status": d.status,
            "attempts": d.attempts,
            "last_error": d.last_error,
            "created_at": d.created_at,
            "updated_at": d.updated_at,
            "task": self._dump_task(task),
        }

    # ───────────────────────── Agent CRUD ─────────────────────────
    def list_agents(self, enabled_only: bool = False) -> list[dict[str, Any]]:
        stmt = select(AgentAgent)
        if enabled_only:
            stmt = stmt.where(col(AgentAgent.enabled) == True)  # noqa: E712
        rows = list(self.db.exec(stmt).all())
        rows.sort(key=lambda a: a.name)
        return [self._dump_agent(a) for a in rows]

    def get_agent(self, agent_id: str) -> dict[str, Any]:
        a = self.db.get(AgentAgent, agent_id)
        if a is None:
            raise NotFoundError(f"agent 不存在：{agent_id}")
        return self._dump_agent(a)

    def create_agent(self, body: AgentCreate) -> dict[str, Any]:
        name = body.name.strip()
        if not name:
            raise ValidationError("name 不能为空")
        a = AgentAgent(
            name=name,
            description=body.description,
            capabilities=list(body.capabilities),
            callback_url=body.callback_url,
            enabled=body.enabled,
        )
        self.db.add(a)
        self.db.commit()
        self.db.refresh(a)
        out = self._dump_agent(a)
        event_bus.publish("agents.agent.created", out, source="agents")
        return out

    def update_agent(self, agent_id: str, body: AgentUpdate) -> dict[str, Any]:
        a = self.db.get(AgentAgent, agent_id)
        if a is None:
            raise NotFoundError(f"agent 不存在：{agent_id}")
        if body.name is not None:
            name = body.name.strip()
            if not name:
                raise ValidationError("name 不能为空")
            a.name = name
        if body.description is not None:
            a.description = body.description
        if body.capabilities is not None:
            a.capabilities = list(body.capabilities)
        if body.enabled is not None:
            a.enabled = body.enabled
        if body.callback_url is not None:
            a.callback_url = body.callback_url or None
        if body.load is not None:
            a.load = body.load
        self.db.add(a)
        self.db.commit()
        self.db.refresh(a)
        out = self._dump_agent(a)
        event_bus.publish("agents.agent.updated", out, source="agents")
        return out

    def delete_agent(self, agent_id: str) -> None:
        a = self.db.get(AgentAgent, agent_id)
        if a is None:
            raise NotFoundError(f"agent 不存在：{agent_id}")
        self.db.delete(a)
        self.db.commit()
        event_bus.publish("agents.agent.deleted", {"id": agent_id}, source="agents")

    # ───────────────────────── Task CRUD ─────────────────────────
    def list_tasks(
        self, status: str | None = None, assignee: str | None = None
    ) -> list[dict[str, Any]]:
        stmt = select(AgentTask)
        if status:
            if status not in TASK_STATUS:
                raise ValidationError(f"status 非法：{status}（合法：{', '.join(TASK_STATUS)}）")
            stmt = stmt.where(col(AgentTask.status) == status)
        if assignee is not None:
            stmt = stmt.where(col(AgentTask.assignee) == assignee)
        rows = list(self.db.exec(stmt).all())
        rows.sort(key=lambda t: (t.priority, t.created_at), reverse=False)
        return [self._dump_task(t) for t in rows]

    def get_task(self, task_id: str) -> dict[str, Any]:
        t = self.db.get(AgentTask, task_id)
        if t is None:
            raise NotFoundError(f"任务不存在：{task_id}")
        return self._dump_task(t)

    def create_task(self, body: TaskCreate) -> dict[str, Any]:
        title = body.title.strip()
        if not title:
            raise ValidationError("title 不能为空")
        if body.mode is not None and body.mode not in DISPATCH_MODE:
            raise ValidationError(f"mode 非法：{body.mode}（合法：{', '.join(DISPATCH_MODE)}）")
        t = AgentTask(
            title=title,
            description=body.description,
            status="draft",
            assignee=body.assignee,
            priority=body.priority,
            inputs=list(body.inputs),
            outputs=list(body.outputs),
            acceptance=list(body.acceptance),
            constraints=list(body.constraints),
            payload=dict(body.payload),
            mode=body.mode,
            callback_url=body.callback_url,
            source=body.source,
        )
        self.db.add(t)
        self.db.commit()
        self.db.refresh(t)
        out = self._dump_task(t)
        event_bus.publish("agents.task.created", out, source="agents")
        return out

    def update_task(self, task_id: str, body: TaskUpdate) -> dict[str, Any]:
        t = self.db.get(AgentTask, task_id)
        if t is None:
            raise NotFoundError(f"任务不存在：{task_id}")
        if t.status == "done":
            # done 之后不可再改（只能新建）
            raise ValidationError("done 状态的任务不可再修改（只能新建）")
        if body.title is not None:
            title = body.title.strip()
            if not title:
                raise ValidationError("title 不能为空")
            t.title = title
        if body.description is not None:
            t.description = body.description
        if body.assignee is not None:
            t.assignee = body.assignee or None
        if body.priority is not None:
            t.priority = body.priority
        if body.status is not None:
            self._assert_transition(t.status, body.status)
            t.status = body.status
            if body.status == "running" and t.started_at is None:
                t.started_at = utcnow()
            if body.status in ("done", "failed", "cancelled") and t.finished_at is None:
                t.finished_at = utcnow()
        if body.inputs is not None:
            t.inputs = list(body.inputs)
        if body.outputs is not None:
            t.outputs = list(body.outputs)
        if body.acceptance is not None:
            t.acceptance = list(body.acceptance)
        if body.constraints is not None:
            t.constraints = list(body.constraints)
        if body.payload is not None:
            t.payload = dict(body.payload)
        if body.mode is not None:
            if body.mode not in DISPATCH_MODE:
                raise ValidationError(f"mode 非法：{body.mode}（合法：{', '.join(DISPATCH_MODE)}）")
            t.mode = body.mode
        if body.callback_url is not None:
            t.callback_url = body.callback_url or None
        self.db.add(t)
        self.db.commit()
        self.db.refresh(t)
        out = self._dump_task(t)
        event_bus.publish("agents.task.updated", out, source="agents")
        return out

    def delete_task(self, task_id: str) -> None:
        t = self.db.get(AgentTask, task_id)
        if t is None:
            raise NotFoundError(f"任务不存在：{task_id}")
        if t.status == "done":
            raise ValidationError("done 状态的任务不可删除")
        # 先删派发记录，避免外键悬挂
        for d in self.db.exec(
            select(AgentDispatch).where(AgentDispatch.task_id == task_id)
        ).all():
            self.db.delete(d)
        self.db.flush()
        self.db.delete(t)
        self.db.commit()
        event_bus.publish("agents.task.deleted", {"id": task_id}, source="agents")

    # ───────────────────────── 派发 / 回报（离线） ─────────────────────────
    def _assert_transition(self, current: str, target: str) -> None:
        if target not in TASK_STATUS:
            raise ValidationError(f"status 非法：{target}（合法：{', '.join(TASK_STATUS)}）")
        if target not in _ALLOWED_TRANSITIONS.get(current, set()):
            raise ValidationError(f"状态不可从 {current} 变为 {target}")

    def dispatch(self, task_id: str, body: DispatchIn) -> dict[str, Any]:
        t = self.db.get(AgentTask, task_id)
        if t is None:
            raise NotFoundError(f"任务不存在：{task_id}")
        if t.status not in _DISPATCHABLE:
            allowed = ", ".join(sorted(_DISPATCHABLE))
            raise ValidationError(f"当前状态 {t.status} 不可派发（可派发：{allowed}）")
        if body.mode not in DISPATCH_MODE:
            raise ValidationError(f"mode 非法：{body.mode}（合法：{', '.join(DISPATCH_MODE)}）")

        agent_name: str | None = None
        target = body.mode
        if body.agent_id is not None:
            agent = self.db.get(AgentAgent, body.agent_id)
            if agent is None:
                raise NotFoundError(f"agent 不存在：{body.agent_id}")
            if not agent.enabled:
                raise ValidationError(f"agent 已停用：{agent.name}")
            agent_name = agent.name
            target = agent.callback_url or body.mode
            agent.load = (agent.load or 0) + 1
            agent.last_seen = utcnow()
            self.db.add(agent)

        dispatch_id = uuid4().hex
        d = AgentDispatch(
            task_id=t.id,
            dispatch_id=dispatch_id,
            mode=body.mode,
            target=target or "",
            status="sent",
            attempts=1,
        )
        self.db.add(d)

        # 离线推进状态：draft/failed → queued；已在 queued 则保持
        if t.status in ("draft", "failed"):
            t.status = "queued"
        t.assignee = agent_name or t.assignee
        t.mode = body.mode
        t.dispatch_id = dispatch_id
        t.attempts = (t.attempts or 0) + 1
        if t.started_at is None:
            t.started_at = utcnow()
        self.db.add(t)
        self.db.commit()
        self.db.refresh(d)
        self.db.refresh(t)
        out = self._dump_dispatch(d, t)
        event_bus.publish("agents.task.dispatched", out, source="agents")
        return out

    def report(self, task_id: str, body: ReportIn) -> dict[str, Any]:
        t = self.db.get(AgentTask, task_id)
        if t is None:
            raise NotFoundError(f"任务不存在：{task_id}")
        if t.status == "done":
            raise ValidationError("done 状态的任务不可再回报（只能新建）")
        if t.status == "cancelled":
            raise ValidationError("cancelled 状态的任务不可回报")

        t.result = body.result
        if body.outputs is not None:
            t.outputs = list(body.outputs)

        rs = (body.result_status or "").strip() or None
        if rs is not None:
            if rs not in ("done", "failed", "cancelled", "running"):
                raise ValidationError(
                    f"result_status 非法：{rs}（合法：done / failed / cancelled / running）"
                )
            t.result_status = rs
            if rs in ("done", "failed", "cancelled"):
                self._assert_transition(t.status, rs)
                t.status = rs
                t.finished_at = utcnow()
            elif rs == "running" and t.status != "running":
                self._assert_transition(t.status, "running")
                t.status = "running"
                if t.started_at is None:
                    t.started_at = utcnow()

        self.db.add(t)
        self.db.commit()
        self.db.refresh(t)
        out = self._dump_task(t)
        event_bus.publish("agents.task.reported", out, source="agents")
        return out

    # ───────────────────────── 概览 ─────────────────────────
    def summary(self) -> SummaryOut:
        tasks = list(self.db.exec(select(AgentTask)).all())
        agents = list(self.db.exec(select(AgentAgent)).all())
        counts = {s: 0 for s in TASK_STATUS}
        for t in tasks:
            if t.status in counts:
                counts[t.status] += 1
        return SummaryOut(
            tasks_total=len(tasks),
            draft=counts["draft"],
            queued=counts["queued"],
            running=counts["running"],
            done=counts["done"],
            failed=counts["failed"],
            cancelled=counts["cancelled"],
            agents_total=len(agents),
            agents_enabled=sum(1 for a in agents if a.enabled),
        )
