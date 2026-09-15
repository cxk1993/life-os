"""calendar_event 参考实现（T04 · 步骤 8）——★ 其它插件照这个改，不要从零发明。

本文件是**范例**，不是可运行插件。各插件卡照抄三样东西：
  1. CalendarEvent 模型（含索引与自关联）      → services/api/modules/<id>/api/models.py
  2. 0001_init.py 迁移写法                     → services/api/modules/<id>/api/migrations/0001_init.py
  3. 取某周事件树（含子事件、跨天）的查询写法  → services/api/modules/<id>/api/service.py

字段契约 = 总纲 §1.5 + 任务卡 T04 详细要求 #2：
  title, color, start_at, end_at, all_day, parent_id(自关联, 层级≤3),
  sort, span_days, source(manual|obsidian|ai), external_ref, location, note

嵌套规则：parent_id 指向父事件；层级最多 3 层（service 层校验，见下）。
跨天规则：end_at 可跨自然日（如周五 20:00 → 周六 02:00），span_days 记录跨越天数。
索引理由：
  - ix_calendar_event_start_at  ：按周/按日查主查询路径
  - ix_calendar_event_parent_id ：组装事件树时取子事件
  - ix_calendar_event_source    ：按来源过滤（Obsidian 导入 / AI 生成）
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import Text as SAText
from sqlmodel import Field, Session, SQLModel, select

from db.base import PkMixin, TimestampMixin, TimestampTZ, utcnow

# ════════════════════════════════════════════════════════════════
# 1. 模型 —— 照这个改（改表名前缀与业务字段）
# ════════════════════════════════════════════════════════════════


class CalendarEvent(PkMixin, TimestampMixin, SQLModel, table=True):
    """日程事件。表名前缀必须是插件 id：calendar_"""

    __tablename__ = "calendar_event"
    __table_args__ = ()

    title: str = Field(max_length=200)
    color: str = Field(default="var(--accent)", max_length=32)  # 设计令牌，不许硬编码色值
    start_at: datetime = Field(sa_type=TimestampTZ, index=True)
    end_at: datetime = Field(sa_type=TimestampTZ, index=True)
    all_day: bool = Field(default=False)

    # 自关联 = 色块嵌套色块；层级 ≤3 由 service 层保证（见 MAX_DEPTH）
    parent_id: str | None = Field(
        default=None, foreign_key="calendar_event.id", index=True
    )
    sort: int = Field(default=0)
    span_days: int = Field(default=1)
    source: str = Field(default="manual", max_length=16, index=True)  # manual|obsidian|ai
    external_ref: str | None = Field(default=None, max_length=200)
    location: str | None = Field(default=None, max_length=200)
    note: str | None = Field(default=None, sa_column=SAText)


MAX_DEPTH = 3


# ════════════════════════════════════════════════════════════════
# 2. 迁移 —— 照这个改（放到 modules/<id>/api/migrations/0001_init.py）
# ════════════════════════════════════════════════════════════════
MIGRATION_TEMPLATE = '''
"""calendar 插件初始化建表。文件建了就不要改，要改就加 0002_xxx.py。"""


def upgrade(engine) -> None:
    # 用 SQLModel 的 metadata 建表即可，避免手写 DDL 出错
    from modules.calendar.api.models import CalendarEvent  # 改这里
    CalendarEvent.__table__.create(bind=engine, checkfirst=True)


def downgrade(engine) -> None:
    from modules.calendar.api.models import CalendarEvent  # 改这里
    CalendarEvent.__table__.drop(bind=engine, checkfirst=True)
'''


# ════════════════════════════════════════════════════════════════
# 3. 查询写法 —— 取某周所有事件（含子事件），一次查询组装成树
# ════════════════════════════════════════════════════════════════


def to_utc(value: str | datetime) -> datetime:
    """任意时间输入统一成 UTC。**必须带时区**，naive 直接报错（铁律）。"""
    if isinstance(value, str):
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        dt = value
    if dt.tzinfo is None:
        raise ValueError("时间必须带时区，例如 2026-09-15T08:00:00+08:00")
    return dt.astimezone(timezone.utc)


def week_range(any_day: date) -> tuple[datetime, datetime]:
    """某天所在周的 [周一 00:00, 下周一 00:00)，UTC。"""
    monday = any_day - timedelta(days=any_day.weekday())
    start = datetime(monday.year, monday.month, monday.day, tzinfo=timezone.utc)
    return start, start + timedelta(days=7)


def events_of_week(session: Session, any_day: date) -> list[dict[str, Any]]:
    """取某周所有事件（含子事件），组装成树。

    ★ 一次查询，禁止循环里再查库（N+1 是模板黑名单）。
    ★ 跨天事件按 [start_at, end_at) 与本周区间相交判定。
    """
    week_start, week_end = week_range(any_day)
    rows = session.exec(
        select(CalendarEvent).where(
            CalendarEvent.start_at < week_end,
            CalendarEvent.end_at > week_start,
        )
    ).all()

    children: dict[str, list[CalendarEvent]] = {}
    roots: list[CalendarEvent] = []
    for r in rows:
        if r.parent_id:
            children.setdefault(r.parent_id, []).append(r)
        else:
            roots.append(r)

    def attach(node: CalendarEvent, depth: int) -> dict[str, Any]:
        if depth > MAX_DEPTH:  # 服务端兜底：父(1)/子(2)/孙(3) 合法，第 4 层拒绝
            raise ValueError(f"事件嵌套超过 {MAX_DEPTH} 层：{node.id}")
        data: dict[str, Any] = {
            "id": node.id,
            "title": node.title,
            "color": node.color,
            "start_at": node.start_at.isoformat(),  # 带时区 ISO8601
            "end_at": node.end_at.isoformat(),
            "all_day": node.all_day,
            "span_days": node.span_days,
            "source": node.source,
            "children": [
                attach(c, depth + 1)
                for c in sorted(children.get(node.id, []), key=lambda x: (x.sort, x.start_at))
            ],
        }
        return data

    return [attach(r, 1) for r in sorted(roots, key=lambda x: (x.start_at, x.sort))]


def assert_nestable(session: Session, parent: CalendarEvent) -> None:
    """创建子事件前的层级校验（service 层职责）。"""
    depth = 1
    cur: CalendarEvent | None = parent
    while cur is not None:
        depth += 1
        cur = session.get(CalendarEvent, cur.parent_id) if cur.parent_id else None
    if depth > MAX_DEPTH:
        raise ValueError(f"嵌套最多 {MAX_DEPTH} 层（父链已有 {depth - 1} 层）")


# ════════════════════════════════════════════════════════════════
# 使用示例（造数据 → 取一周事件树 → 跨天往返）
# ════════════════════════════════════════════════════════════════
def demo(session: Session) -> None:
    tz = timezone(timedelta(hours=8))  # 主人本地时区
    fri_20 = datetime(2026, 9, 18, 20, 0, tzinfo=tz)

    parent = CalendarEvent(title="周五晚会·复习周", start_at=fri_20,
                           end_at=fri_20 + timedelta(hours=6))  # 跨到周六 02:00
    session.add(parent)
    session.commit()
    session.refresh(parent)

    child = CalendarEvent(title="无机化学", parent_id=parent.id, sort=1,
                          start_at=fri_20, end_at=fri_20 + timedelta(hours=2))
    grandchild = CalendarEvent(title="第三章 习题", parent_id=child.id, sort=1,
                               start_at=fri_20, end_at=fri_20 + timedelta(minutes=45))
    session.add(child)
    session.add(grandchild)
    session.commit()

    tree = events_of_week(session, date(2026, 9, 18))
    print(tree[0]["title"], "→", [c["title"] for c in tree[0]["children"]])
