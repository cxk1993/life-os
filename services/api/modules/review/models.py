"""插件模型：复盘（Work-Review 只读接入）。

★ 表名必须以插件 id 为前缀（review_），否则内核拒绝建表。
★ 时间列一律用 db.base.TimestampTZ（UTC 存储 + 往返保时区）。
★ Mixin 里的字段只能用 sa_type=（用 sa_column= 会在多表继承时抛
  "Column object ... already assigned to Table"）。

表：
  review_daily  某日工作复盘落库（date 唯一，幂等 upsert）
  review_note   主人批注（与机器日报分开存，不写回 Work-Review）

★ raw_path 是**来源标识**（形如 work-review:<date>），不是文件路径。
  contracts/data-dictionary.md 已登记 review_daily；raw_md / review_note
  的字典登记需求见 docs/issues 或 T09 报告，不改别人的行。
"""
from __future__ import annotations

from datetime import date as DateType
from datetime import datetime

from sqlalchemy import Date
from sqlalchemy import Text as SAText
from sqlmodel import Field

from db.base import PkMixin, TimestampMixin, TimestampTZ


class ReviewDaily(PkMixin, TimestampMixin, table=True):
    """某日复盘。date 唯一；重复 ingest 覆盖而非追加。"""

    __tablename__ = "review_daily"
    __table_args__ = {"extend_existing": True}

    # 本地日历日（YYYY-MM-DD），主业务键
    date: DateType = Field(sa_type=Date, unique=True, index=True)
    # 类别时长 JSON：[{name, seconds, duration_text}, ...]
    category_json: str | None = Field(default=None, sa_type=SAText)
    # 应用使用明细 JSON
    app_json: str | None = Field(default=None, sa_type=SAText)
    # 网站访问明细 JSON
    domain_json: str | None = Field(default=None, sa_type=SAText)
    # 24 小时活跃度 JSON
    hourly_json: str | None = Field(default=None, sa_type=SAText)
    # AI 分析 Markdown
    ai_analysis_md: str | None = Field(default=None, sa_type=SAText)
    # 原始日报 Markdown（来自 export-markdown）
    raw_md: str | None = Field(default=None, sa_type=SAText)
    # 来源标识：work-review:<date>（不是磁盘路径）
    raw_path: str = Field(default="", max_length=120)
    # 当日上游返回空（优雅降级，不崩）
    is_empty: bool = Field(default=False)
    # 最近一次成功同步时间
    synced_at: datetime | None = Field(default=None, sa_type=TimestampTZ)


class ReviewNote(PkMixin, TimestampMixin, table=True):
    """主人自己的批注。不写回 review_daily，更不写回 Work-Review。"""

    __tablename__ = "review_note"
    __table_args__ = {"extend_existing": True}

    date: DateType = Field(sa_type=Date, index=True)
    content_md: str = Field(sa_type=SAText)
