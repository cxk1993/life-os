"""U2 小日历 · 日聚合只读查询（day_peek / day_dots）。

跨 calendar/todo/diary(docs)/review **只读聚合**，零新表。
供顶栏小日历 peek 与右侧今日栏共用。
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

from sqlmodel import Session, col, select


def _day_range(d: date) -> tuple[datetime, datetime]:
    start = datetime.combine(d, time.min)
    return start, start + timedelta(days=1)


def day_dots(db: Session, start: date, end: date) -> dict[str, list[str]]:
    """月视图打点：date → ["calendar","todo",...]（有内容的源）。"""
    marks: dict[str, set[str]] = {}
    s0 = datetime.combine(start, time.min)
    s1 = datetime.combine(end, time.min) + timedelta(days=1)

    def mark(dt: datetime | None, kind: str) -> None:
        if dt is None:
            return
        if s0 <= dt < s1:
            marks.setdefault(dt.date().isoformat(), set()).add(kind)

    try:
        from modules.calendar.models import CalendarEvent  # type: ignore

        for ev in db.exec(select(CalendarEvent)).all():
            mark(getattr(ev, "start_at", None) or getattr(ev, "start", None), "calendar")
    except Exception:
        pass
    try:
        from modules.todo.models import TodoItem  # type: ignore

        for it in db.exec(select(TodoItem)).all():
            if getattr(it, "done", False) or getattr(it, "status", "") == "done":
                continue
            mark(getattr(it, "due", None) or getattr(it, "due_at", None), "todo")
    except Exception:
        pass
    return {k: sorted(v) for k, v in sorted(marks.items())}


def day_peek(db: Session, d: date) -> dict[str, Any]:
    """单日聚合：marks + list（calendar/diary/review/todo）。"""
    s0, s1 = _day_range(d)
    out: dict[str, Any] = {
        "date": d.isoformat(),
        "marks": {"calendar": 0, "diary": 0, "review": 0, "todo_open": 0},
        "dots": {"has_event": False, "has_diary": False, "has_review": False, "has_todo": False},
        "list": {"calendar": [], "diary": [], "review": [], "todo": []},
    }
    # calendar
    try:
        from modules.calendar.models import CalendarEvent  # type: ignore

        for ev in db.exec(select(CalendarEvent)).all():
            st = getattr(ev, "start_at", None) or getattr(ev, "start", None)
            if st and s0 <= st < s1:
                out["list"]["calendar"].append(
                    {"id": str(getattr(ev, "id", "")), "title": getattr(ev, "title", ""), "start": st.isoformat()}
                )
    except Exception:
        pass
    # todo
    try:
        from modules.todo.models import TodoItem  # type: ignore

        for it in db.exec(select(TodoItem)).all():
            due = getattr(it, "due", None) or getattr(it, "due_at", None)
            done = bool(getattr(it, "done", False) or getattr(it, "status", "") == "done")
            if due and s0 <= due < s1 and not done:
                out["list"]["todo"].append(
                    {"id": str(getattr(it, "id", "")), "title": getattr(it, "title", ""), "done": False}
                )
    except Exception:
        pass
    # diary / review：日期串匹配 docs 树或 review 表（尽力而为）
    key = d.isoformat()
    short = f"{d.year:04d}/{d.month:02d}/{d.day:02d}"
    try:
        from modules.docs.models import DocsNode  # type: ignore

        for n in db.exec(select(DocsNode)).all():
            name = getattr(n, "name", "") or ""
            path_hint = name + " " + str(getattr(n, "meta_json", "") or "")
            if key in path_hint or short in path_hint:
                out["list"]["diary"].append({"id": str(n.id), "title": name})
    except Exception:
        pass
    try:
        from modules.review.models import ReviewDay  # type: ignore

        for r in db.exec(select(ReviewDay)).all():
            day = getattr(r, "day", None) or getattr(r, "date", None)
            ds = day.isoformat() if hasattr(day, "isoformat") else str(day or "")
            if ds == key:
                out["list"]["review"].append({"id": str(getattr(r, "id", "")), "title": ds})
    except Exception:
        pass

    out["marks"] = {
        "calendar": len(out["list"]["calendar"]),
        "diary": len(out["list"]["diary"]),
        "review": len(out["list"]["review"]),
        "todo_open": len(out["list"]["todo"]),
    }
    out["dots"] = {
        "has_event": out["marks"]["calendar"] > 0,
        "has_diary": out["marks"]["diary"] > 0,
        "has_review": out["marks"]["review"] > 0,
        "has_todo": out["marks"]["todo_open"] > 0,
    }
    return out
