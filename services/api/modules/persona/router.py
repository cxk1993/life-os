"""人格体系路由（★ 极薄：只保留 health + manifest）。

T16 是 T15 文档树内核的**薄壳**：不建任何业务表、不认识"人格"概念。
所有数据读写全走 T15 的 `docs.node.*` / `docs.search` 能力（经内核 API），
本模块只提供健康检查 + manifest（内核要求每个插件必有）。

★ 前缀由内核按 manifest.api.base 自动加，这里不要写 prefix=。
"""

import json
from pathlib import Path

from fastapi import APIRouter

router = APIRouter()

_MANIFEST_PATH = Path(__file__).resolve().parent / "manifest.json"
with _MANIFEST_PATH.open(encoding="utf-8") as _f:
    _MANIFEST = json.load(_f)


@router.get("/health")
def health() -> dict[str, bool]:
    """每个插件都必须有 health —— 内核据此判断"该能力是否可用"。"""
    return {"ok": True}


@router.get("/manifest")
def manifest() -> dict:
    """模块清单（前端 / AI 发现能力用）。"""
    return _MANIFEST
