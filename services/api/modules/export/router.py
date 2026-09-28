"""export 路由：profiles / 预览（V1 只读，zip 落盘候派）。"""
import json
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from fastapi import Path as FPath
from typing import Annotated

from core.deps import get_current_user

from .packager import PROFILES, package_preview

router = APIRouter()

_MANIFEST_PATH = Path(__file__).resolve().parent / "manifest.json"
with _MANIFEST_PATH.open(encoding="utf-8") as _f:
    _MANIFEST = json.load(_f)


@router.get("/health")
def health() -> dict[str, bool]:
    """插件健康探针（恒 200）。"""
    return {"ok": True}


@router.get("/manifest")
def manifest() -> dict:
    """模块清单（前端 / AI 发现能力用）。"""
    return _MANIFEST


@router.get("/profiles")
def profiles() -> dict[str, Any]:
    """列出可用的导出档案（profile）—— 每一项是一个「搬家包」模板。"""
    return {"items": [{"id": k, "title": v} for k, v in PROFILES.items()]}


@router.get("/preview/{profile}")
def preview(
    profile: Annotated[str, FPath(description="档案 id —— 从 GET /profiles 的结果里取")],
    _user: Annotated[Any, Depends(get_current_user)] = None,
) -> dict[str, Any]:
    """预览某个档案**会导出什么**（只报数量，不真导出）。"""
    return package_preview(profile, {"todo": 0, "calendar": 0, "docs": 0})
