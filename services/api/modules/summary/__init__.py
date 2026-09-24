"""今日摘要聚合模块（U2 · 小日历聚合）。

提供 `GET /api/v1/summary/today` 端点，
并发聚合 calendar/todo/diary/review 的 today-summary 数据。
"""
from .router import router

__all__ = ["router"]