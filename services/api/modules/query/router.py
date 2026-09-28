"""query 路由：Q1 预置查询（只读）。"""
import json
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from fastapi import Path as FPath
from typing import Annotated

from core.deps import get_current_user, get_db

from .presets import PRESETS, run_preset

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


@router.get("/presets")
def presets() -> dict[str, Any]:
    """列出内置查询预设（id + 标题），供前端做快捷入口。"""
    return {
        "items": [
            {"id": qid, "title": qid.replace("q_", "").replace("_", " ")}
            for qid in sorted(PRESETS)
        ]
    }


@router.get("/presets/{qid}")
def run(
    qid: Annotated[str, FPath(description="预置查询 id —— 从 GET /presets 的结果里取")],
    days: int | None = Query(None, description="近 N 天（不传则用该预置的默认窗口）"),
    db: Annotated[Any, Depends(get_db)] = None,
    _user: Annotated[Any, Depends(get_current_user)] = None,
) -> dict[str, Any]:
    """days：参数化范围（近 N 天）；不传走各预置默认窗（向前兼容）。"""
    return run_preset(db, qid, days=days)
