"""TX-TODO-REMIND-01 · 待办到期提醒调度（复用 calendar 三段式范式，workbuddy 2026-09-25）。

★ 主人令「做」：待办此前**从未接入推送**（`grep scheduler|push` 在 todo 模块 0 命中）。

链路（与 calendar 完全同构，ADR-0002 不跨模块 import 插件本体）：
    due_scheduler 扫到期
      → event_bus.publish("todo.item.due")
        → push.link 监听（push 模块）
          → web push（浏览器/PWA 通知）

设计要点：
- **env 开关**：`TODO_REMIND_ENABLED=true` 才起（与 calendar 同款纪律，默认关）。
- **轮询**：默认 60s（env `TODO_REMIND_POLL_SECONDS`）。
- **窗口**：只提醒 **最近 DUE_WINDOW_SECONDS（默认 300s）内到期**的待办 ——
  这样**重启后不会补发一堆历史提醒**（内存幂等集合丢失也无害，天然规避重复）。
- **幂等**：进程内 `_notified` 集合（配合窗口 = 不会重复、不会轰炸）。
- **不打断**：任何异常只 warning，绝不影响主进程与其它调度。
"""
from __future__ import annotations

import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlmodel import Session, select

from core.events import event_bus

from .models import TodoItem

log = logging.getLogger("todo.due")

EVENT_DUE = "todo.item.due"
DEFAULT_POLL_SECONDS = 60
DEFAULT_DUE_WINDOW_SECONDS = 300  # 只看 5 分钟内到期的（防重启补发历史）

_lock_state: dict[str, Any] = {"scheduler": None}
_notified: set[str] = set()


def _enabled() -> bool:
    return os.environ.get("TODO_REMIND_ENABLED", "false").lower() == "true"


def _poll_seconds() -> int:
    try:
        return max(10, int(os.environ.get("TODO_REMIND_POLL_SECONDS", DEFAULT_POLL_SECONDS)))
    except ValueError:
        return DEFAULT_POLL_SECONDS


def _due_window_seconds() -> int:
    try:
        return max(60, int(os.environ.get("TODO_REMIND_WINDOW_SECONDS", DEFAULT_DUE_WINDOW_SECONDS)))
    except ValueError:
        return DEFAULT_DUE_WINDOW_SECONDS


def collect_due_todos(db: Session, *, now: datetime | None = None) -> list[TodoItem]:
    """收集**刚刚进入提醒窗口**的待办（未完成 + due_at 落在窗口内 + 未提醒过）。"""
    now = now or datetime.now(UTC)
    window_start = now - timedelta(seconds=_due_window_seconds())
    rows = db.exec(
        select(TodoItem).where(
            TodoItem.done == False,  # noqa: E712 — SQLModel 表达式需 == False
            TodoItem.due_at.is_not(None),  # type: ignore[union-attr]
            TodoItem.due_at <= now,  # type: ignore[operator]
            TodoItem.due_at >= window_start,  # type: ignore[operator]
        )
    ).all()
    return [r for r in rows if r.id not in _notified]


def run_due_tick(db: Session) -> int:
    """一轮扫描：对到期待办发布 `todo.item.due` 事件。返回发布条数。"""
    due = collect_due_todos(db)
    sent = 0
    for item in due:
        try:
            event_bus.publish(
                {
                    "topic": EVENT_DUE,
                    "payload": {
                        "item_id": item.id,
                        "title": item.text,
                        "due_at": item.due_at.isoformat() if item.due_at else "",
                        "priority": item.priority or "",
                    },
                }
            )
            sent += 1
        except Exception as exc:  # noqa: BLE001 — 单条失败不影响其它待办
            log.warning("publish todo.item.due failed: %s", exc)
        _notified.add(item.id)  # 无论发布成功与否都记账（防每轮重试轰炸）
    if sent:
        log.info("待办到期提醒已发布", extra={"count": sent})
    return sent


def start_scheduler() -> bool:
    """Interval 调度：默认关（`TODO_REMIND_ENABLED=true` 开启）。与 calendar 同模式。"""
    if not _enabled():
        log.info("待办提醒未启用（TODO_REMIND_ENABLED!=true）")
        return False
    if _lock_state.get("scheduler") is not None:
        return False

    from apscheduler.schedulers.background import (
        BackgroundScheduler,  # type: ignore[import-untyped]
    )

    def _job() -> None:
        # ★ 根因 D/令 7 纪律：非 Depends 场景必须用 db_session()（get_db 是生成器依赖）
        from core.deps import db_session

        try:
            with db_session() as db:
                run_due_tick(db)
        except Exception as exc:  # noqa: BLE001 — tick 失败不打断主进程
            log.warning("todo due tick failed: %s", exc)

    sched = BackgroundScheduler(timezone="Asia/Shanghai")
    sched.add_job(_job, "interval", seconds=_poll_seconds(), id="todo_due_tick")
    sched.start()
    _lock_state["scheduler"] = sched
    log.info(
        "待办到期提醒调度已启动",
        extra={"poll_seconds": _poll_seconds(), "window_seconds": _due_window_seconds()},
    )
    return True


def stop_scheduler() -> None:
    sched = _lock_state.get("scheduler")
    if sched is not None:
        sched.shutdown(wait=False)
        _lock_state["scheduler"] = None


def scheduler_status() -> dict[str, Any]:
    return {
        "enabled": _enabled(),
        "running": _lock_state.get("scheduler") is not None,
        "poll_seconds": _poll_seconds(),
        "window_seconds": _due_window_seconds(),
        "notified_in_process": len(_notified),
    }
