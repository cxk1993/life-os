"""web（网页工作台）路由（薄：只做参数校验 + 调 service）。

HTTP 契约（全项目统一，不许自创）：
  成功 → 直接返回资源 JSON（200/201）
  失败 → 由内核统一转成 RFC7807 application/problem+json

★ 前缀由内核按 manifest.api.base 自动加，这里**不要写 prefix=**。
★ 不自己捕获异常包成自定义格式，内核统一处理（ValidationError → 400，NotFoundError → 404）。
★ 事件在 service 层 publish，内核 SSE 自动下推，这里不重复发。
★ 幂等（Idempotency-Key）由内核 IdempotencyMiddleware 自动处理。
★ 路径参数用 Annotated[str, FPath(...)]（不是 = FPath(...)）：
  后者是"带默认值的参数"，会逼后面的 body 也必须给默认值。
★ 相对导入是**可以**用的：本插件 kind=builtin，内核走包导入
  （`importlib.import_module("modules.web.router")`，见 core/plugins/discover.py:151）。
  —— 生成器模板里那句"不能用 from .xxx import"是对**第三方插件**（按文件路径加载）说的；
  内置插件不受此限，现有 10 个内置插件的 router.py 全都用了相对导入。
★ 本文件**不要**加 `from __future__ import annotations`：
  它会把 `-> None` 变成字符串 "None" → get_type_hints 得到 NoneType（truthy）
  → FastAPI 认为 204 带了响应体 → 建路由时 AssertionError → **整个后端起不来**。
"""

import json
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from fastapi import Path as FPath
from sqlmodel import Session

from core.deps import get_current_user, get_db
from core.security import User

from .schema import FrameUrlOut, TouchOut, WebEntryCreate, WebEntryListOut, WebEntryOut, WebEntryUpdate
from .service import WebEntryService

router = APIRouter()

_MANIFEST_PATH = Path(__file__).resolve().parent / "manifest.json"
with _MANIFEST_PATH.open(encoding="utf-8") as _f:
    _MANIFEST = json.load(_f)

# ★ 依赖别名**只做类型**，不要把 Depends 塞进 Annotated。
DbDep = Session
UserDep = User


@router.get("/health")
def health() -> dict[str, bool]:
    """每个插件都必须有 health —— 内核据此判断"该能力是否可用"。"""
    return {"ok": True}


@router.get("/manifest")
def manifest() -> dict:
    """模块清单（前端 / AI 发现能力用）。"""
    return _MANIFEST


@router.get("/entries", response_model=WebEntryListOut)
def list_entries(
    enabled: bool | None = Query(None, description="true 只看启用的；缺省看全部"),
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    items, total = WebEntryService(db).list_entries(enabled=enabled)
    return {"items": items, "total": total}


@router.post("/entries", response_model=WebEntryOut, status_code=status.HTTP_201_CREATED)
def create_entry(
    body: WebEntryCreate,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    # 校验（url schema / auth_ref 形状 / kind 枚举）集中在 schema 的 normalize_*
    # 与 service，路由层不散写校验。
    return WebEntryService(db).create(body)


@router.get("/entries/{entry_id}", response_model=WebEntryOut)
def get_entry(
    entry_id: Annotated[str, FPath(description="条目 id")],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    svc = WebEntryService(db)
    return svc.dump(svc.get(entry_id))


@router.patch("/entries/{entry_id}", response_model=WebEntryOut)
def update_entry(
    entry_id: Annotated[str, FPath(description="条目 id")],
    body: WebEntryUpdate,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    return WebEntryService(db).update(entry_id, body)


@router.delete("/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(
    entry_id: Annotated[str, FPath(description="条目 id")],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> None:
    WebEntryService(db).delete(entry_id)


@router.post("/entries/{entry_id}/touch", response_model=TouchOut)
def touch_entry(
    entry_id: Annotated[str, FPath(description="条目 id")],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> TouchOut:
    """记一次「打开」。v0.1 只回时间戳（端点先在，便于以后加使用统计）。"""
    return TouchOut(**WebEntryService(db).touch(entry_id))

@router.get("/entries/{entry_id}/frame-url", response_model=FrameUrlOut)
def frame_url(
    entry_id: Annotated[str, FPath(description="条目 id")],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> FrameUrlOut:
    """返回 iframe 内嵌用的真实 URL（含 auth_ref 解析后的凭据）。

    ★ 条目表永不明文凭据：auth_ref 形如 "pat:env:PI_TOKEN"，运行时从 os.environ 取。
    ★ 解析失败（env 变量缺失）→ 422 + 错误详情，不吞异常。
    ★ 无 auth_ref 或 "none" → 直接返回原 url。
    """
    return WebEntryService(db).frame_url(entry_id)
