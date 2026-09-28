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
    """插件健康探针（恒 200）。"""
    return {"ok": True}


@router.get("/manifest")
def manifest() -> dict:
    """模块清单（前端 / AI 发现能力用）。"""
    return _MANIFEST


@router.get("", response_model=list[HabitOut])
def list_habits(
    include_archived: bool = Query(
        False, description="是否连**已归档**的习惯一起返回（默认 false = 只看在用的）"
    ),
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """列出习惯（每条自带 `today_status` 与 `streak`，前端不用再算）。"""
    return HabitsService(db).list_habits(include_archived)


@router.get("/summary", response_model=SummaryOut)
def summary(
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> SummaryOut:
    """今日概览：应打卡数 / 已打卡 / 待打卡 / 休息 / 最长连续（给 dashboard 卡片用）。"""
    return HabitsService(db).summary()

@router.post("", response_model=HabitOut, status_code=status.HTTP_201_CREATED)
def create_habit(
    body: HabitCreate,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """新建一个习惯（含频率规则 `rule` 与休息日 `rest_weekdays`）。"""
    return HabitsService(db).create(body)


@router.get("/{habit_id}", response_model=HabitOut)
def get_habit(
    habit_id: Annotated[str, FPath()],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """读单个习惯（含今日状态与连续天数）。"""
    return HabitsService(db).get(habit_id)


@router.patch("/{habit_id}", response_model=HabitOut)
def update_habit(
    habit_id: Annotated[str, FPath()],
    body: HabitUpdate,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """改习惯（名字/目标/频率/颜色/提醒时间/休息日/归档/排序）。

    ⚠️ `archived=true` 是**归档**（软隐藏，历史打卡仍在）；想彻底删用 DELETE。
    """
    return HabitsService(db).update(habit_id, body)


@router.delete("/{habit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_habit(
    habit_id: Annotated[str, FPath()],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> None:
    """删除习惯（**连它的打卡历史一并删除**，不可恢复；只想停用请改用 PATCH 归档）。"""
    HabitsService(db).delete(habit_id)


@router.post("/{habit_id}/checkin", response_model=HabitOut)
def checkin(
    habit_id: Annotated[str, FPath()],
    body: CheckIn,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """给某个习惯**打卡**（返回更新后的习惯，含最新 streak）。

    `date` 省略 = 今天（按 Asia/Shanghai）；补打过去的日子请显式传 `date`。
    """
    return HabitsService(db).checkin(habit_id, body)


@router.delete("/{habit_id}/checkin/{day}", response_model=HabitOut)
def uncheck(
    habit_id: Annotated[str, FPath()],
    day: Annotated[DateType, FPath(description="YYYY-MM-DD 本地日历日")],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """**撤销**某个习惯在某一天的打卡（打错了用它，day 是本地日历日）。"""
    return HabitsService(db).uncheck(habit_id, day)


@router.get("/{habit_id}/logs", response_model=list[LogOut])
def list_logs(
    habit_id: Annotated[str, FPath()],
    frm: DateType | None = Query(
        None, alias="from", description="起始日（YYYY-MM-DD，本地日历日）；不传=不限"
    ),
    to: DateType | None = Query(
        None, description="结束日（YYYY-MM-DD，本地日历日）；不传=不限"
    ),
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """某个习惯的**打卡历史**（可按日期区间过滤；日期是日历日不是时刻）。"""
    return HabitsService(db).list_logs(habit_id, frm, to)
