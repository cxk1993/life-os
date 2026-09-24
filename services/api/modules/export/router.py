"""export 路由：profiles / 预览（V1 只读，zip 落盘候派）。"""
import json
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends

from core.deps import get_current_user

from .packager import PROFILES, package_preview

router = APIRouter()

_MANIFEST_PATH = Path(__file__).resolve().parent / "manifest.json"
with _MANIFEST_PATH.open(encoding="utf-8") as _f:
    _MANIFEST = json.load(_f)


@router.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@router.get("/manifest")
def manifest() -> dict:
    return _MANIFEST


@router.get("/profiles")
def profiles() -> dict[str, Any]:
    return {"items": [{"id": k, "title": v} for k, v in PROFILES.items()]}


@router.get("/preview/{profile}")
def preview(
    profile: str,
    _user: Annotated[Any, Depends(get_current_user)] = None,
) -> dict[str, Any]:
    return package_preview(profile, {"todo": 0, "calendar": 0, "docs": 0})
