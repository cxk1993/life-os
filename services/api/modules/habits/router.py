"""习惯打卡路由（薄：参数校验 + 调 service）。

★ 前缀由内核按 manifest.api.base 自动加，这里不要写 prefix=。
★ 路径参数用 Annotated[str, FPath(...)]；本文件不要加 future import。
★ 204 端点写 `-> None`（已去掉 future import，安全）。
"""
import json
from datetime import date as DateType
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from fastapi import Path as FPath
from sqlmodel import Session

from core.deps import get_current_user, get_db
from core.security import User

from .schema import CheckIn, HabitCreate, HabitOut, HabitUpdate, LogOut, SummaryOut
from .service import HabitsService

router = APIRouter()

_MANIFEST_PATH = Path(__file__).resolve().parent / "manifest.json"
with _MANIFEST_PATH.open(encoding="utf-8") as _f:
    _MANIFEST = json.load(_f)

DbDep = Session
UserDep = User


@router.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@router.get("/manifest")
def manifest() -> dict:
    return _MANIFEST


@router.get("/habits", response_model=list[HabitOut])
def list_habits(
    include_archived: bool = Query(False),
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> list[dict[str, Any]]:
    return HabitsService(db).list_habits(include_archived)


@router.post("/habits", response_model=HabitOut, status_code=status.HTTP_201_CREATED)
def create_habit(
    body: HabitCreate,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    return HabitsService(db).create(body)


@router.get("/habits/{habit_id}", response_model=HabitOut)
def get_habit(
    habit_id: Annotated[str, FPath()],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    return HabitsService(db).get(habit_id)


@router.patch("/habits/{habit_id}", response_model=HabitOut)
def update_habit(
    habit_id: Annotated[str, FPath()],
    body: HabitUpdate,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    return HabitsService(db).update(habit_id, body)


@router.delete("/habits/{habit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_habit(
    habit_id: Annotated[str, FPath()],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> None:
    HabitsService(db).delete(habit_id)


@router.post("/habits/{habit_id}/checkin", response_model=HabitOut)
def checkin(
    habit_id: Annotated[str, FPath()],
    body: CheckIn,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    return HabitsService(db).checkin(habit_id, body)


@router.delete("/habits/{habit_id}/checkin/{day}", response_model=HabitOut)
def uncheck(
    habit_id: Annotated[str, FPath()],
    day: Annotated[DateType, FPath(description="YYYY-MM-DD 本地日历日")],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    return HabitsService(db).uncheck(habit_id, day)


@router.get("/habits/{habit_id}/logs", response_model=list[LogOut])
def list_logs(
    habit_id: Annotated[str, FPath()],
    frm: DateType | None = Query(None, alias="from"),
    to: DateType | None = Query(None),
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> list[dict[str, Any]]:
    return HabitsService(db).list_logs(habit_id, frm, to)


@router.get("/summary", response_model=SummaryOut)
def summary(
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> SummaryOut:
    return HabitsService(db).summary()
