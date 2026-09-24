"""日程表路由（薄：只做参数校验 + 调 service + 发事件）。

HTTP 契约（全项目统一，不许自创）：
  成功 → 直接返回资源 JSON（200/201）
  失败 → 由内核统一转成 RFC7807 application/problem+json

★ 前缀由内核按 manifest.api.base 自动加，这里**不要写 prefix=**。
★ 不自己捕获异常包成自定义格式，内核统一处理。
★ 事件总线：写操作 publish 到 event_bus，内核 SSE（/api/v1/events/subscribe）自动下推。
★ 内部一律用包路径导入（from modules.calendar.xxx import ...），不要相对导入。
★ 路径参数用 Annotated[str, FPath(...)]（不是 = FPath(...)）：
  后者是「带默认值的参数」，会逼后面的 body 也必须给默认值，mypy 报
  non-default argument follows default argument；前者没有默认值，body 可以必填。
★ 本文件**不要**加 `from __future__ import annotations`：
  它会把 `-> None` 变成字符串 "None" → get_type_hints 得到 NoneType（truthy）
  → FastAPI 认为 204 带了响应体 → 整个后端起不来。
"""
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, status
from fastapi import Path as FPath
from sqlmodel import Session

from core.config import get_settings
from core.deps import get_current_user, get_db
from core.events import event_bus
from core.security import User

from .schema import EventCreate, EventOut, EventUpdate, FreeSlotOut
from .service import CalendarService

router = APIRouter()

_MANIFEST_PATH = Path(__file__).resolve().parent / "manifest.json"
with _MANIFEST_PATH.open(encoding="utf-8") as _f:
    _MANIFEST = json.load(_f)

# ★ 依赖别名**只做类型**，不要把 Depends 塞进 Annotated：
#   标准写法：db: Session = Depends(get_db)，FastAPI 与 mypy 都满意。
DbDep = Session
UserDep = User


def _emit(topic: str, payload: dict) -> None:
    event_bus.publish(topic, payload=payload, source="calendar")


@router.get("/health")
def health() -> dict[str, bool]:
    """每个插件都必须有 health —— 内核据此判断"该能力是否可用"。"""
    return {"ok": True}


@router.get("/manifest")
def manifest() -> dict:
    """模块清单（前端 / AI 发现能力用）。"""
    return _MANIFEST


@router.get("/events", response_model=list[EventOut])
def list_events(
    frm: str = Query(..., alias="from"),
    to: str = Query(...),
    include_children: bool = Query(True),
    flat: bool = Query(False),
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> list[dict]:
    return CalendarService(db).list_range(frm, to, include_children, flat)


@router.get("/today-summary")
def today_summary(
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict:
    """U2 聚合数据源（令 62）：当日事件列表 + 条数。

    ★ 形状按 docs/specs/today-summary数据源规范-v1.md；BFF（/api/v1/summary/today）
    原样透传本响应（R-1：内核不解析业务）。
    ★ 三态：200（本端点，items 可为空 = 今天没事件）· 401 = 未鉴权。
    """
    tz = ZoneInfo("Asia/Shanghai")  # 主人时区；多时区配置候 v2
    now = datetime.now(tz)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    events = CalendarService(db).list_range(
        day_start.astimezone(UTC).isoformat(),
        day_end.astimezone(UTC).isoformat(),
        include_children=False,
        flat=True,
    )
    items = []
    for e in events[:5]:  # 规范：items ≤ 5，超出聚合
        start = str(e.get("start_at", "") or "")
        hhmm = start[11:16] if len(start) >= 16 else ""
        title = str(e.get("title", "") or "")
        items.append({"text": f"{hhmm} {title}".strip(), "state": "info"})
    return {
        "title": "今日日程",
        "items": items,
        "count": len(events),
        "link": "/calendar",
    }


@router.post("/events", response_model=EventOut, status_code=status.HTTP_201_CREATED)
def create_event(
    body: EventCreate,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict:
    out = CalendarService(db).create(body)
    _emit("calendar.event.created", out)
    return out


@router.get("/events/{event_id}", response_model=EventOut)
def get_event(
    event_id: Annotated[str, FPath(...)],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict:
    return CalendarService(db).get_tree(event_id)


@router.patch("/events/{event_id}", response_model=EventOut)
def update_event(
    event_id: Annotated[str, FPath(...)],
    body: EventUpdate,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict:
    out = CalendarService(db).update(event_id, body)
    _emit("calendar.event.updated", out)
    return out


@router.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(
    event_id: Annotated[str, FPath(...)],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> None:
    CalendarService(db).delete(event_id)
    _emit("calendar.event.deleted", {"id": event_id})


@router.post(
    "/events/{event_id}/children",
    response_model=EventOut,
    status_code=status.HTTP_201_CREATED,
)
def add_child(
    event_id: Annotated[str, FPath(...)],
    body: EventCreate,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict:
    out = CalendarService(db).add_child(event_id, body)
    _emit("calendar.event.created", out)
    return out


@router.patch("/events/{event_id}/children/{child_id}", response_model=EventOut)
def update_child(
    event_id: Annotated[str, FPath(...)],
    child_id: Annotated[str, FPath(...)],
    body: EventUpdate,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict:
    out = CalendarService(db).update_child(event_id, child_id, body)
    _emit("calendar.event.updated", out)
    return out


@router.delete(
    "/events/{event_id}/children/{child_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_child(
    event_id: Annotated[str, FPath(...)],
    child_id: Annotated[str, FPath(...)],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> None:
    CalendarService(db).delete_child(event_id, child_id)
    _emit("calendar.event.deleted", {"id": child_id, "parent_id": event_id})


@router.get("/free-slots", response_model=list[FreeSlotOut])
def free_slots(
    date: str = Query(
        ...,
        description="YYYY-MM-DD，按主人本地时区（settings.tz，默认 Asia/Shanghai）的自然日计算",
    ),
    min_hours: float = Query(1.0, ge=0.5),
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> list[FreeSlotOut]:
    # ★ 不能按 UTC 切天：主人说"10 月 1 日"指的是**本地**那一天。
    #   按 UTC 切会把本地 01:00-03:00 的事件（= UTC 前一天 17:00）漏掉，
    #   于是 free_slots 返回"全天空闲 24h"（实测踩过，2 条验收因此挂掉）。
    tz = ZoneInfo(get_settings().tz)
    day_start = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=tz)
    return CalendarService(db).free_slots(day_start, min_hours)


# ── T25 提醒调度（默认关；详见 modules/calendar/reminder_scheduler.py）──
from .reminder_scheduler import (  # noqa: E402
    list_reminder_logs,
    run_reminder_tick,
    scheduler_status,
    start_scheduler,
)


@router.get("/reminders/scheduler")
def get_reminder_scheduler_status(
    _user: UserDep = Depends(get_current_user),
) -> dict:
    """T25：提醒调度状态（enabled/running/lead/poll）。不暴露密钥。"""
    return scheduler_status()


@router.post("/reminders/tick")
def post_reminder_tick(
    lead_minutes: int = Query(default=None, ge=0, le=1440),
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict:
    """T25：手动触发一轮到期扫描（验收/排障用；不依赖定时是否开启）。"""
    items = run_reminder_tick(db, lead_minutes=lead_minutes)
    return {"ok": True, "count": len(items), "items": items}


@router.get("/reminders/logs")
def get_reminder_logs(
    limit: int = Query(default=50, ge=1, le=200),
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> list[dict]:
    """T25：最近提醒投递日志（持久化去重证据）。"""
    return list_reminder_logs(db, limit=limit)


try:
    start_scheduler()
except Exception as _rs_exc:  # noqa: BLE001
    import logging

    logging.getLogger("calendar.reminder").warning("calendar 提醒调度启动失败: %s", _rs_exc)
