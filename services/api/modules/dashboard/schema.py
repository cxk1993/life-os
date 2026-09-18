"""dashboard 出入参。

★ 概览是聚合器：不持有业务数据，数字全部来自其它模块 API。
★ 单模块失败/超时用 {"status": "timeout"|"error"} 降级，整包 overview 不 500。
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ModuleStatusOut(BaseModel):
    """一个上游模块的健康条目。"""

    id: str
    name: str
    status: Literal["ok", "timeout", "error"] = "ok"
    detail: str = ""
    path: str = ""
    elapsed_ms: int | None = None


class TodayCountsOut(BaseModel):
    """今日数字（None = 对应模块不可用，前端显示「—」）。"""

    calendar_events: int | None = None
    todo_open: int | None = None
    habits_done: int | None = None
    habits_total: int | None = None


class TodayOut(BaseModel):
    """今日合并视图（日程 + 待办 + 习惯）。"""

    date: str
    calendar: dict[str, Any] = Field(default_factory=dict)
    todo: dict[str, Any] = Field(default_factory=dict)
    habits: dict[str, Any] = Field(default_factory=dict)
    counts: TodayCountsOut = Field(default_factory=TodayCountsOut)


class MoneyOut(BaseModel):
    """钱：BeeCount 快照 + 本地账本汇总。"""

    snapshot: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)


class ReviewOut(BaseModel):
    """复盘：取数来源 / 最近 ingest。"""

    source: dict[str, Any] = Field(default_factory=dict)


class GrowthOut(BaseModel):
    """成长罗盘：最小闭环先返回空轴 + 占位说明（完整三轴后补）。"""

    axes: list[dict[str, Any]] = Field(default_factory=list)
    placeholder: str = "完整成长罗盘后补：三轴条目与 PATCH 写接口将在后续任务卡落地"


class CardHintOut(BaseModel):
    """声明了 dashboard.card 扩展点的插件提示（前端用 SlotHost 渲染真卡片）。"""

    pluginId: str
    name: str
    slot: str = "dashboard.card"
    enabled: bool = True


class OverviewOut(BaseModel):
    """GET /overview：首屏一次取全。

    date / today / money / review / system / cards / cards_hint / growth / meta
    """

    date: str
    today: TodayOut
    money: MoneyOut
    review: ReviewOut
    growth: GrowthOut = Field(default_factory=GrowthOut)
    system: list[ModuleStatusOut] = Field(default_factory=list)
    cards: list[CardHintOut] = Field(default_factory=list)
    cards_hint: str = (
        "其它插件挂在 dashboard.card 上的卡片由前端 SlotHost 渲染"
        "（calendar / todo / habits / agents 已声明该扩展点）"
    )
    meta: dict[str, Any] = Field(default_factory=dict)


class HealthOfSystemOut(BaseModel):
    """GET /health-of-system：各模块健康灯。"""

    date: str
    system: list[ModuleStatusOut] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class HealthOut(BaseModel):
    """插件自身探活。"""

    ok: bool = True
