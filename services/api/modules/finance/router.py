"""插件路由：理财。

HTTP 契约（全项目统一，不许自创）：
  成功 → 直接返回资源 JSON（200/201）
  失败 → 由内核统一转成 RFC7807 application/problem+json

★ 加数据库路由时，照 `docs/示例/calendar_event_示例.py` 的写法；
  注意 models.py 与 router.py 都是被内核**按文件路径**加载的，
  所以两者之间**不能用 `from .models import ...` 相对导入**（见下面的写法）。
"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> dict[str, bool]:
    """每个插件都必须有 health —— 内核据此判断"该能力是否可用"。"""
    return {"ok": True}
