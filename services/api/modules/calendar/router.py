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
from datetime import datetime
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
