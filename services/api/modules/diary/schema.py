"""diary 出入参定义（薄壳：都是定位/视图端点）。

★ 出参直接返回资源 JSON，不包 {code,data}。
★ 本卡不建表，无时间列（由 T15 的 docs_* 管）。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DiaryEntryOut(BaseModel):
    """某日日记定位结果。"""

    node_id: str
    path: str
    exists: bool
    date: str


class DiaryTodayOut(BaseModel):
    """今天（按 settings.tz）。"""

    date: str
    node_id: str
    path: str
    exists: bool


class DiaryMonthOut(BaseModel):
    """某月已有日记的日期集合。"""

    year: int
    month: int
    days: list[str] = Field(default_factory=list)


class DiaryInboxOut(BaseModel):
    """收件箱条目。"""

    items: list[dict] = Field(default_factory=list)


class DiaryCaptureOut(BaseModel):
    """随手记结果。"""

    node_id: str
    path: str
    name: str


class DiaryConsolidateIn(BaseModel):
    """归纳请求。"""

    node_id: str = Field(description="收件箱节点 id")
    date: str = Field(description="目标日期 YYYY-MM-DD")


class DiaryConsolidateOut(BaseModel):
    """归纳结果。"""

    node_id: str
    target_date: str
    target_month_node: str
