"""健康路由（薄：校验 + 调 service）。

★ 前缀由内核按 manifest 加，这里不写 prefix。
★ 本文件不要加 future import；204 端点不要写 -> None 返回注解时注意兼容。
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
    FollowupRequestOut,
    HealthRecordCreate,
    HealthRecordOut,
    HealthRecordUpdate,
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
    return {"ok": True}


@router.get("/manifest")
def manifest() -> dict:
    return _MANIFEST


@router.get("/records", response_model=list[HealthRecordOut])
def list_records(
    kind: str | None = Query(default=None),
    frm: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None),
    followup_only: bool = Query(default=False),
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> list[dict[str, Any]]:
    return HealthService(db).list_records(
        kind=kind, date_from=frm, date_to=to, followup_only=followup_only
    )


@router.get("/records/{record_id}", response_model=HealthRecordOut)
def get_record(
    record_id: Annotated[str, FPath(...)],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    return HealthService(db).get(record_id)


@router.post("/records", response_model=HealthRecordOut, status_code=status.HTTP_201_CREATED)
def create_record(
    body: HealthRecordCreate,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    return HealthService(db).create(body)


@router.patch("/records/{record_id}", response_model=HealthRecordOut)
def update_record(
    record_id: Annotated[str, FPath(...)],
    body: HealthRecordUpdate,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    return HealthService(db).update(record_id, body)


@router.delete("/records/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_record(
    record_id: Annotated[str, FPath(...)],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> None:
    HealthService(db).delete(record_id)


@router.post(
    "/records/{record_id}/request-followup",
    response_model=FollowupRequestOut,
)
def request_followup(
    record_id: Annotated[str, FPath(...)],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """手动再触发跟进事件（只 publish，不 import todo）。"""
    return HealthService(db).request_followup(record_id)
