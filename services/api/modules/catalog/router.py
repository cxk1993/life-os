"""能力目录路由（薄层：参数校验 + 调 service）。

★ 前缀由内核按 manifest.api.base 自动加，这里不写 prefix=。
★ 不自己捕获异常，内核统一转 RFC7807。
★ plugin 源 = request.app.state.modules（注册表实时，不缓存）；
★ web_entry 源 = get_plugin_client 跨插件调 T19（ISSUE-005 A 案通道）。
★ 本文件不要加 `from __future__ import annotations`（204 端点会崩，见 T19 注释）。
"""
import json
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, status
from fastapi import Path as FPath
from sqlmodel import Session

from core.deps import get_current_user, get_db, get_plugin_client
from core.security import User

from .schema import CapabilityEntryOut, CatalogOut, ManualEntryCreate, ManualEntryUpdate
from .service import CatalogService

router = APIRouter()

_MANIFEST_PATH = Path(__file__).resolve().parent / "manifest.json"
with _MANIFEST_PATH.open(encoding="utf-8") as _f:
    _MANIFEST = json.load(_f)

# ★ 依赖别名只做类型，不要把 Depends 塞进 Annotated。
DbDep = Session
UserDep = User

# 本插件要跨插件调 T19 的 web.entry.read 能力（在 manifest.requires 声明了）
_WEB_CAPS = ["web.entry.read", "web.entry.write"]


@router.get("/health")
def health() -> dict[str, bool]:
    """每个插件都必须有 health —— 内核据此判断「该能力是否可用」。"""
    return {"ok": True}


@router.get("/manifest")
def manifest() -> dict:
    """模块清单（前端 / AI 发现能力用）。"""
    return _MANIFEST


@router.get("", response_model=CatalogOut)
def get_catalog(
    request: Request,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """四源合并 → 全量能力目录（场景 C 的入口）。

    ★ 这就是「接口说明页」的机器可读形态：agent 拿 token → 调这个 → 自助配置。
    """
    modules: dict[str, Any] = getattr(request.app.state, "modules", {})
    # 跨插件调 T19：requires 已声明 web.entry.read；失败时 service 内部降级为不含 web_entry
    try:
        client = get_plugin_client(request, _WEB_CAPS)
    except Exception:
        client = None  # T19 不可用 → 目录降级（不含 web_entry 源），不报错
    return CatalogService(db).catalog(modules, client)


@router.post("/manual", response_model=CapabilityEntryOut, status_code=status.HTTP_201_CREATED)
def create_manual(
    body: ManualEntryCreate,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """新建手动条目（对齐 T19 校验：url / auth_ref / kind）。"""
    return CatalogService(db).create_manual(body)


@router.patch("/manual/{entry_id}", response_model=CapabilityEntryOut)
def update_manual(
    entry_id: Annotated[str, FPath(description="手动条目 id")],
    body: ManualEntryUpdate,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """编辑 / 切 enabled 开关。"""
    return CatalogService(db).update_manual(entry_id, body)


@router.delete("/manual/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_manual(
    entry_id: Annotated[str, FPath(description="手动条目 id")],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> None:
    """删除手动条目。"""
    CatalogService(db).delete_manual(entry_id)