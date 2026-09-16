"""插件模型：todo_item（待办与周期清单）。

★ 表名必须以插件 id 为前缀（todo_）。
★ 时间列一律用 db.base.TimestampTZ（UTC 存储 + 往返保时区）。
★ Mixin 里的字段只能用 sa_type=（用 sa_column= 会在多表继承时抛
  "Column object ... already assigned to Table"）。

字段设计：
  text        任务正文（不含复选框/元数据）
  done        是否完成
  done_at     完成时间（UTC）；周期任务每次完成都写
  due_at      截止时间（UTC，可带时分）
  priority    high / medium / low
  recur_rule  RRULE（如 FREQ=WEEKLY;BYDAY=SU）或原文
  tags        JSON 数组字符串（SQLite 无数组类型）
  source_path 来自哪个笔记文件（导入时记录）
  source_line 在原文件中的行号
  sort        手动排序权重
  series_id   周期任务链 id（同一条周期任务的所有实例共享）
  instance_no 周期实例序号（第几个，从 0 计）
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from sqlmodel import Field

from db.base import PkMixin, TimestampMixin, TimestampTZ


class TodoItem(PkMixin, TimestampMixin, table=True):
    """一条待办。周期任务的"下一次实例"是独立的一行，共享 series_id。"""

    __tablename__ = "todo_item"
    __table_args__ = {"extend_existing": True}

    text: str = Field(max_length=500)
    done: bool = Field(default=False, index=True)
    done_at: Optional[datetime] = Field(default=None, sa_type=TimestampTZ, index=True)
    due_at: Optional[datetime] = Field(default=None, sa_type=TimestampTZ, index=True)
    priority: Optional[str] = Field(default=None, max_length=8)  # high|medium|low
    recur_rule: Optional[str] = Field(default=None, max_length=200)  # RRULE 或原文
    tags: Optional[str] = Field(default=None)  # JSON 列表
    source_path: Optional[str] = Field(default=None, max_length=500)
    source_line: Optional[int] = Field(default=None)
    sort: int = Field(default=0)
    series_id: Optional[str] = Field(default=None, index=True)  # 周期链 id
    instance_no: int = Field(default=0)


def tags_from_json(raw: Optional[str]) -> list[str]:
    """DB 里的 tags 字符串 → 列表（空/非法 → []）。"""
    if not raw:
        return []
    try:
        val = json.loads(raw)
        return [str(t) for t in val] if isinstance(val, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def tags_to_json(tags: list[str]) -> Optional[str]:
    """列表 → DB 字符串（空列表 → None，不占空间）。"""
    if not tags:
        return None
    return json.dumps([str(t) for t in tags], ensure_ascii=False)
