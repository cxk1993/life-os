"""课程表业务逻辑。

★ 事件在本层 publish，内核 SSE 自动下推（与 todo/habits 同款）。
★ 周次表达式解析：`1-16` / `1,3,5-16` / `2-16双`（双周）/ `1-15单`（单周）。
  空表达式 = 每周都上。
★ 循环里禁止查库：一次拿全表，内存过滤。
"""
from __future__ import annotations

from datetime import date as DateType
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlmodel import Session, select

from core.errors import NotFoundError, ValidationError
from core.events import event_bus

from .models import WEEKDAY_NAMES, CourseItem
from .schema import CourseCreate, CourseUpdate

SH_TZ = ZoneInfo("Asia/Shanghai")

EVENT_CREATED = "course.item.created"
EVENT_UPDATED = "course.item.updated"
EVENT_DELETED = "course.item.deleted"


def local_today() -> DateType:
    return datetime.now(SH_TZ).date()


def _parse_weeks(raw: str | None) -> set[int] | None:
    """周次表达式 → 周次集合。None / 空 → None（= 每周都上）。"""
    if not raw or not raw.strip():
        return None
    text = raw.strip()
    parity: str | None = None
    if text.endswith("双"):
        parity, text = "even", text[:-1]
    elif text.endswith("单"):
        parity, text = "odd", text[:-1]
    out: set[int] = set()
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, _, b = part.partition("-")
            try:
                lo, hi = int(a), int(b)
            except ValueError as exc:
                raise ValidationError(f"周次表达式非法：{raw}") from exc
            if lo > hi:
                lo, hi = hi, lo
            out.update(range(lo, hi + 1))
        else:
            try:
                out.add(int(part))
            except ValueError as exc:
                raise ValidationError(f"周次表达式非法：{raw}") from exc
    if parity == "even":
        out = {w for w in out if w % 2 == 0}
    elif parity == "odd":
        out = {w for w in out if w % 2 == 1}
    return out


def _term_week(term_start: str | None, day: DateType) -> int | None:
    """给定学期起始日（第一周周一附近），算 day 落在第几教学周（1 起）。"""
    if not term_start:
        return None
    try:
        start = datetime.strptime(term_start, "%Y-%m-%d").date()
    except ValueError:
        return None
    delta = (day - start).days
    if delta < 0:
        return None
    return delta // 7 + 1


def _row_out(row: CourseItem) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "teacher": row.teacher,
        "location": row.location,
        "weekday": row.weekday,
        "start_section": row.start_section,
        "end_section": row.end_section,
        "start_time": row.start_time,
        "end_time": row.end_time,
        "weeks": row.weeks,
        "term_start": row.term_start,
        "note": row.note,
        "enabled": row.enabled,
        "sort": row.sort,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _sort_key(row: CourseItem) -> tuple[int, str, int, int]:
    """网格内排序：有时间的按时间，没时间的按节次，再按 sort。"""
    return (0 if row.start_time else 1, row.start_time or "", row.start_section or 99, row.sort)


class CourseService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ── 读 ──────────────────────────────────────────────────────────
    def list_items(self, *, weekday: int | None = None, enabled_only: bool = False) -> list[dict]:
        stmt = select(CourseItem)
        if weekday is not None:
            stmt = stmt.where(CourseItem.weekday == weekday)
        if enabled_only:
            stmt = stmt.where(CourseItem.enabled == True)  # noqa: E712
        rows = list(self.db.exec(stmt).all())
        rows.sort(key=lambda r: (r.weekday, *_sort_key(r)))
        return [_row_out(r) for r in rows]

    def get(self, item_id: str) -> dict[str, Any]:
        row = self.db.get(CourseItem, item_id)
        if row is None:
            raise NotFoundError(f"课程不存在：{item_id}")
        return _row_out(row)

    def week_grid(self, *, day: DateType | None = None, term_start: str | None = None) -> dict:
        """一周课表网格：days 恒 7 列（周一…周日）。

        term_start：优先用请求参数，其次取「课数据里最近出现的 term_start」。
        有 weeks 表达式的课：只有命中当前周次才出现；否则每周都出现。
        """
        day = day or local_today()
        monday = day - timedelta(days=day.weekday())
        rows = list(self.db.exec(select(CourseItem).where(CourseItem.enabled == True)).all())  # noqa: E712

        ts = term_start
        if not ts:
            for r in rows:
                if r.term_start:
                    ts = r.term_start
                    break
        cur_week = _term_week(ts, day)

        days: list[dict[str, Any]] = []
        for wd in range(7):
            target = monday + timedelta(days=wd)
            cell: list[dict[str, Any]] = []
            for r in rows:
                if r.weekday != wd:
                    continue
                weeks = _parse_weeks(r.weeks)
                if weeks is not None:
                    ref_ts = r.term_start or ts
                    w = _term_week(ref_ts, target)
                    if w is None or w not in weeks:
                        continue
                cell.append(_row_out(r))
            cell.sort(key=lambda c: _sort_key_by_dict(c))
            days.append(
                {
                    "weekday": wd,
                    "label": WEEKDAY_NAMES[wd],
                    "items": cell,
                }
            )
        return {"days": days, "term_start": ts, "term_week": cur_week}

    # ── 写 ──────────────────────────────────────────────────────────
    def create(self, body: CourseCreate) -> dict[str, Any]:
        data = body.model_dump()
        data["name"] = str(data["name"]).strip()
        if not data["name"]:
            raise ValidationError("课名不能为空")
        _parse_weeks(data.get("weeks"))  # 校验表达式合法性（非法直接 400）
        row = CourseItem(**data)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        event_bus.publish(EVENT_CREATED, payload=_row_out(row), source="course")
        return _row_out(row)

    def update(self, item_id: str, body: CourseUpdate) -> dict[str, Any]:
        row = self.db.get(CourseItem, item_id)
        if row is None:
            raise NotFoundError(f"课程不存在：{item_id}")
        patch = body.model_dump(exclude_unset=True)
        if "weeks" in patch:
            _parse_weeks(patch.get("weeks"))
        if "name" in patch and not str(patch["name"] or "").strip():
            raise ValidationError("课名不能为空")
        for k, v in patch.items():
            setattr(row, k, v)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        event_bus.publish(EVENT_UPDATED, payload=_row_out(row), source="course")
        return _row_out(row)

    def delete(self, item_id: str) -> None:
        row = self.db.get(CourseItem, item_id)
        if row is None:
            raise NotFoundError(f"课程不存在：{item_id}")
        self.db.delete(row)
        self.db.commit()
        event_bus.publish(EVENT_DELETED, payload={"id": item_id}, source="course")


def _sort_key_by_dict(c: dict[str, Any]) -> tuple[int, str, int, int]:
    return (0 if c.get("start_time") else 1, c.get("start_time") or "", c.get("start_section") or 99, c.get("sort") or 0)
