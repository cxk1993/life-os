"""日记路由（薄壳：定位/视图端点，数据读写经 T15 的 HTTP API）。

★ 前缀由内核按 manifest.api.base 自动加，这里不要写 prefix=。
★ 本卡不直连 docs_* 表 —— 通过 httpx 调 T15 的 /api/v1/docs/...（requires 已声明）。
★ 跨插件鉴权：用当前用户 sub 签一个短时 token 注入 Authorization。
★ 本文件不要加 `from __future__ import annotations`（204 端点的坑）。
"""

import json
import os
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from core.deps import get_current_user, get_db
from core.errors import ValidationError
from core.security import User, create_access_token

from .schema import (
    DiaryCaptureOut,
    DiaryConsolidateIn,
    DiaryConsolidateOut,
    DiaryEntryOut,
    DiaryInboxOut,
    DiaryMonthOut,
    DiaryTodayOut,
)
from .service import DiaryService

router = APIRouter()

_MANIFEST_PATH = Path(__file__).resolve().parent / "manifest.json"
with _MANIFEST_PATH.open(encoding="utf-8") as _f:
    _MANIFEST = json.load(_f)

DbDep = Session
UserDep = User

# 内部 API 基址：同进程内直接打本服务（测试/本地都是 127.0.0.1:18000）
_API_BASE = os.environ.get("INTERNAL_API_BASE", "http://127.0.0.1:18000")


class _HttpxDocsAdapter:
    """T15 docs API 的 httpx 适配器（带鉴权 token）。"""

    def __init__(self, token: str, base: str = _API_BASE) -> None:
        self._token = token
        self._base = base
        self._headers = {"Authorization": f"Bearer {token}"}

    def _req(self, method: str, path: str, **kw: Any) -> Any:
        with httpx.Client(base_url=self._base, headers=self._headers, timeout=10) as c:
            r = c.request(method, path, **kw)
            if r.status_code >= 400:
                raise ValidationError(
                    f"docs API {method} {path} → HTTP {r.status_code}: {r.text[:200]}"
                )
            if r.status_code == 204 or not r.content:
                return None
            return r.json()

    def tree(self) -> list[dict]:
        return self._req("GET", "/api/v1/docs/nodes") or []

    def create(self, parent_id: str | None, kind: str, name: str, meta: dict | None = None) -> dict:
        return self._req(
            "POST",
            "/api/v1/docs/nodes",
            json={"parent_id": parent_id, "kind": kind, "name": name, "meta_json": meta},
        )

    def patch(self, node_id: str, body: dict) -> dict:
        return self._req("PATCH", f"/api/v1/docs/nodes/{node_id}", json=body)


def _svc(user: UserDep, tz: str = "Asia/Shanghai") -> DiaryService:
    """构造 DiaryService：用当前用户 token 调 docs。"""
    token = create_access_token(user.sub)
    return DiaryService(_HttpxDocsAdapter(token), tz=tz)


@router.get("/health")
def health() -> dict[str, bool]:
    """每个插件都必须有 health —— 内核据此判断"该能力是否可用"。"""
    return {"ok": True}


@router.get("/manifest")
def manifest() -> dict:
    """模块清单。"""
    return _MANIFEST


@router.get("/today", response_model=DiaryTodayOut)
def today(
    db: DbDep = Depends(get_db),
    user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """今天（按 Asia/Shanghai）对应的日记节点。"""
    svc = _svc(user)
    d = svc.today()
    entry = svc.get_or_create_entry(d.isoformat())
    return {
        "date": d.isoformat(),
        "node_id": entry["node_id"],
        "path": entry["path"],
        "exists": entry["exists"],
    }


@router.get("/entry", response_model=DiaryEntryOut)
def get_entry(
    date: str | None = Query(None, description="日期 YYYY-MM-DD；缺省=今天"),
    db: DbDep = Depends(get_db),
    user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """定位某日日记（get-or-create 幂等）。"""
    return _svc(user).get_or_create_entry(date)


@router.post("/entry", response_model=DiaryEntryOut)
def ensure_entry(
    date: str | None = Query(None, description="日期 YYYY-MM-DD；缺省=今天"),
    db: DbDep = Depends(get_db),
    user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """确保某日节点存在（get-or-create）。"""
    return _svc(user).get_or_create_entry(date)


@router.get("/month", response_model=DiaryMonthOut)
def month(
    year: int = Query(..., description="年，如 2026"),
    month: int = Query(..., description="月，如 9"),
    db: DbDep = Depends(get_db),
    user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """该月已有日记的日期集合（月历高亮）。"""
    svc = _svc(user)
    days = svc.month_days(year, month)
    return {"year": year, "month": month, "days": days}


@router.get("/inbox", response_model=DiaryInboxOut)
def inbox(
    db: DbDep = Depends(get_db),
    user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """列出收件箱条目。"""
    return {"items": _svc(user).inbox_items()}


@router.post("/capture", response_model=DiaryCaptureOut)
def capture(
    db: DbDep = Depends(get_db),
    user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """随手记：在收件箱下新建一条。"""
    return _svc(user).capture()


@router.post("/consolidate", response_model=DiaryConsolidateOut)
def consolidate(
    body: DiaryConsolidateIn,
    db: DbDep = Depends(get_db),
    user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """归纳：把收件箱条目移到目标日期月份下。"""
    return _svc(user).consolidate(body.node_id, body.date)
