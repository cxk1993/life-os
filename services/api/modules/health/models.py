"""插件模型：健康（T21）。

★ 表名必须 health_ 前缀。
★ 时间列 TimestampTZ（UTC）；Mixin 只用 sa_type=。
★ 同源导入：from modules.health.xxx import ...（包路径）。
"""
from __future__ import annotations

from datetime import date as DateType
from datetime import datetime

from sqlalchemy import Date
from sqlalchemy import Text as SAText
from sqlmodel import Field

from db.base import PkMixin, TimestampMixin, TimestampTZ

KIND_SYMPTOM = "symptom"
KIND_MEDICATION = "medication"
KIND_APPOINTMENT = "appointment"
KIND_LAB = "lab"
KINDS = (KIND_SYMPTOM, KIND_MEDICATION, KIND_APPOINTMENT, KIND_LAB)


class HealthRecord(PkMixin, TimestampMixin, table=True):
    """健康事件记录。表名 health_。"""

    __tablename__ = "health_record"

    kind: str = Field(max_length=16, index=True)
    title: str = Field(max_length=200)
    occurred_at: datetime = Field(sa_type=TimestampTZ, index=True)
    severity: int | None = Field(default=None)
    # 备注 JSON/Text；零业务字段，扩展走这里
    note: str | None = Field(default=None, sa_type=SAText)
    followup_needed: bool = Field(default=False, index=True)
    # 建议跟进日期（日历日，Asia/Shanghai 语义由业务层解释）
    followup_due: DateType | None = Field(default=None, sa_type=Date)
