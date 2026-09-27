"""课程表路由（薄：只做参数校验 + 调 service + 发事件）。

HTTP 契约（全项目统一，不许自创）：
  成功 → 直接返回资源 JSON（200/201）
  失败 → 由内核统一转成 RFC7807 application/problem+json

★ 前缀由内核按 manifest.api.base 自动加，这里**不要写 prefix=**。
★ 路径参数用 Annotated[str, FPath(...)]（不是 = FPath(...)）。
★ 本文件**不要**加 `from __future__ import annotations`：
  它会把 `-> None` 变成字符串 → FastAPI 认为 204 带了响应体 → 后端起不来。
"""
import json
from datetime import date as DateType
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, status
from fastapi import Path as FPath
from sqlmodel import Session

from core.deps import get_current_user, get_db
from core.errors import ValidationError
from core.security import User

from . import remind_scheduler as _remind  # noqa: E402,F401  （导入即装载调度）
from .schema import CourseCreate, CourseOut, CourseUpdate, TermSettingsIn, TermSettingsOut, WeekGridOut  # noqa: E402
from .service import CourseService  # noqa: E402

router = APIRouter()

_MANIFEST_PATH = Path(__file__).resolve().parent / "manifest.json"
with _MANIFEST_PATH.open(encoding="utf-8") as _f:
    _MANIFEST = json.load(_f)

DbDep = Session
UserDep = User
_SH_TZ = ZoneInfo("Asia/Shanghai")


@router.get("/health")
def health() -> dict[str, bool]:
    """每个插件都必须有 health —— 内核据此判断「该能力是否可用」。"""
    return {"ok": True}


@router.get("/manifest")
def manifest() -> dict:
    """模块清单（前端 / AI 发现能力用）。"""
    return _MANIFEST


@router.get("/items", response_model=list[CourseOut])
def list_items(
    weekday: int | None = Query(None, ge=0, le=6, description="0=周一 … 6=周日"),
    enabled_only: bool = Query(False, description="只看启用中的课"),
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> list[dict[str, Any]]:
    return CourseService(db).list_items(weekday=weekday, enabled_only=enabled_only)


@router.post("/items", response_model=CourseOut, status_code=status.HTTP_201_CREATED)
def create_item(
    body: CourseCreate,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    return CourseService(db).create(body)


@router.get("/items/{item_id}", response_model=CourseOut)
def get_item(
    item_id: Annotated[str, FPath(description="课程 id")],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    return CourseService(db).get(item_id)


@router.patch("/items/{item_id}", response_model=CourseOut)
def update_item(
    item_id: Annotated[str, FPath(description="课程 id")],
    body: CourseUpdate,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    return CourseService(db).update(item_id, body)


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(
    item_id: Annotated[str, FPath(description="课程 id")],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> None:
    CourseService(db).delete(item_id)


@router.get("/week", response_model=WeekGridOut)
def week_grid(
    date: str | None = Query(None, description="该周内任意一天（YYYY-MM-DD，默认今天）"),
    term_start: str | None = Query(None, description="学期第一周周一（YYYY-MM-DD）"),
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """一周课表网格（前端 CourseApp 主视图）。"""
    day: DateType | None = None
    if date:
        try:
            day = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValidationError(f"date 需为 YYYY-MM-DD：{date}") from exc
    else:
        day = datetime.now(_SH_TZ).date()
    return CourseService(db).week_grid(day=day, term_start=term_start)


# ═══════ ★ 学期设置（主人令「学期起始日固定」· 存 plugin_setting）═══════
@router.get("/term", response_model=TermSettingsOut)
def get_term(
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """读学期设置（当前只有 term_start）。"""
    return {"term_start": CourseService(db).get_term_start()}


@router.put("/term", response_model=TermSettingsOut)
def put_term(
    body: TermSettingsIn,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """写学期起始日（第一周周一）。传空串/不传 = 清除。"""
    return CourseService(db).set_term_start(body.term_start)


# ═══════ ★ 上课前提醒（复用日历/待办同款三段式）═══════
@router.post("/due/tick")
def post_due_tick(
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict:
    """手动触发一轮「上课前提醒」扫描（验收/排障用）。"""
    from .remind_scheduler import run_course_tick

    return {"ok": True, "count": run_course_tick(db)}


@router.get("/due/scheduler")
def get_due_scheduler_status(
    _user: UserDep = Depends(get_current_user),
) -> dict:
    """上课提醒调度状态（enabled/running/poll/lead）。"""
    from .remind_scheduler import scheduler_status

    return scheduler_status()


try:
    from .remind_scheduler import start_scheduler as _start_course

    _start_course()
except Exception as _exc:  # noqa: BLE001
    import logging

    logging.getLogger("course.remind").warning("上课提醒调度启动失败: %s", _exc)
