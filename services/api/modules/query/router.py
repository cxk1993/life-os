"""query 路由：Q1 预置查询（只读）。"""
import json
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends

from core.deps import get_current_user, get_db

from .presets import PRESETS, run_preset

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


@router.get("/presets")
def presets() -> dict[str, Any]:
    return {
        "items": [
            {"id": qid, "title": qid.replace("q_", "").replace("_", " ")}
            for qid in sorted(PRESETS)
        ]
    }


@router.get("/presets/{qid}")
def run(
    qid: str,
    db: Annotated[Any, Depends(get_db)] = None,
    _user: Annotated[Any, Depends(get_current_user)] = None,
) -> dict[str, Any]:
    return run_preset(db, qid)
