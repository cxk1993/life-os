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


class DiaryEntryUpdateIn(BaseModel):
    """日记编辑请求（CRUD 补全）。

    - title：日记标题（= docs 节点 name）
    - date：目标日期 YYYY-MM-DD（变更 → 移动节点到新日期目录，幂等 get-or-create）
    正文内容编辑走 docs 的 PUT /nodes/{id}/content（本薄壳不重复代理）。
    """

    title: str | None = Field(default=None, max_length=200, description="日记标题")
    date: str | None = Field(default=None, description="目标日期 YYYY-MM-DD")


class DiaryTodayOut(BaseModel):
    """今天（按 settings.tz）。"""

    date: str
    node_id: str
    path: str
    exists: bool


class DiaryTodaySummaryOut(BaseModel):
    """今日日记摘要（U2 小日历聚合 · + 协调令63）。

    规范 v1 形状：{title, items:[{text,state}], link}
    BFF 透传 data（R-1 内核零业务），本模块只返回当日摘要数据。
    """

    title: str
    items: list["DiaryItem"] = []
    link: str


class DiaryItem(BaseModel):
    """摘要条目（规范 v1）。

    state 枚举：info | due | done | alert
    """

    text: str
    state: str = "info"


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
