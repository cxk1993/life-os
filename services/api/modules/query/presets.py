"""TX-QUERY-01 Q1 · 五条预置查询（只读聚合，零新表）。"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

from sqlmodel import Session, col, select


def _today() -> date:
    return date.today()


def _q_open_overdue(db: Session, days: int | None = None) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    try:
        from modules.todo.models import TodoItem  # type: ignore

        end = datetime.combine(_today(), time.min)
        if days is not None and days > 0:
            # 参数化：只看「近 N 天内到期且仍逾期」的
            start = end - timedelta(days=days)
        else:
            start = None
        for it in db.exec(select(TodoItem)).all():
            done = bool(getattr(it, "done", False) or getattr(it, "status", "") == "done")
            due = getattr(it, "due", None) or getattr(it, "due_at", None)
            if not done and due and due < end and (start is None or due >= start):
                rows.append(
                    {"id": str(it.id), "title": getattr(it, "title", ""), "due": due.isoformat()}
                )
    except Exception:
        pass
    rows.sort(key=lambda r: r.get("due") or "")
    return _pack("q_open_overdue", rows, empty_text="今天没有逾期，真棒")


def _q_week_health_open(db: Session, days: int | None = None) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    tags = ("健康", "复诊", "用药")
    try:
        from modules.todo.models import TodoItem  # type: ignore

        horizon = datetime.now() + timedelta(days=days if days and days > 0 else 7)
        for it in db.exec(select(TodoItem)).all():
            done = bool(getattr(it, "done", False) or getattr(it, "status", "") == "done")
            due = getattr(it, "due", None) or getattr(it, "due_at", None)
            title = str(getattr(it, "title", "") or "")
            if done:
                continue
            if due and due > horizon:
                continue
            if any(t in title for t in tags):
                rows.append({"id": str(it.id), "title": title, "due": due.isoformat() if due else None})
    except Exception:
        pass
    return _pack("q_week_health_open", rows, empty_text="本周无健康待办")


def _q_habit_streak_break(db: Session) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    try:
        from modules.habits.models import Habit  # type: ignore

        today = _today()
        for h in db.exec(select(Habit)).all():
            last = getattr(h, "last_check", None) or getattr(h, "last_checked_at", None)
            if last is None:
                rows.append(
                    {
                        "id": str(h.id),
                        "name": getattr(h, "name", ""),
                        "streak": getattr(h, "streak", 0),
                        "last_check": None,
                    }
                )
                continue
            ld = last.date() if hasattr(last, "date") else last
            if ld < today - timedelta(days=1):
                rows.append(
                    {
                        "id": str(h.id),
                        "name": getattr(h, "name", ""),
                        "streak": getattr(h, "streak", 0),
                        "last_check": str(ld),
                    }
                )
    except Exception:
        pass
    rows.sort(key=lambda r: -(r.get("streak") or 0))
    return _pack("q_habit_streak_break", rows, empty_text="全部在连击")


def _q_free_slots_today(db: Session) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    try:
        from modules.calendar.models import CalendarEvent  # type: ignore

        s0 = datetime.combine(_today(), time.min)
        s1 = s0 + timedelta(days=1)
        evs = []
        for ev in db.exec(select(CalendarEvent)).all():
            st = getattr(ev, "start_at", None) or getattr(ev, "start", None)
            en = getattr(ev, "end_at", None) or getattr(ev, "end", None)
            if st and s0 <= st < s1:
                evs.append((st, en or (st + timedelta(hours=1))))
        evs.sort()
        cursor = s0
        for st, en in evs:
            if st > cursor:
                mins = int((st - cursor).total_seconds() // 60)
                rows.append({"start": cursor.isoformat(), "end": st.isoformat(), "minutes": mins})
            cursor = max(cursor, en)
        if cursor < s1:
            mins = int((s1 - cursor).total_seconds() // 60)
            rows.append({"start": cursor.isoformat(), "end": s1.isoformat(), "minutes": mins})
    except Exception:
        pass
    return _pack("q_free_slots_today", rows, empty_text="今天排满了")


def _q_finance_week_sum(db: Session) -> dict[str, Any]:
    income = expense = 0
    try:
        from modules.finance.models import FinanceEntry  # type: ignore

        today = _today()
        start = datetime.combine(today - timedelta(days=today.weekday()), time.min)
        for e in db.exec(select(FinanceEntry)).all():
            d = getattr(e, "date", None) or getattr(e, "occurred_at", None)
            if not d:
                continue
            dd = d.date() if hasattr(d, "date") else d
            dt = datetime.combine(dd, time.min)
            if dt < start:
                continue
            amount = int(getattr(e, "amount", 0) or 0)
            kind = str(getattr(e, "kind", "") or getattr(e, "type", ""))
            if amount >= 0:
                income += amount
            else:
                expense += -amount
        rows = [{"income_sum": income, "expense_sum": expense, "net": income - expense}]
    except Exception:
        rows = []
    return _pack("q_finance_week_sum", rows, empty_text="本周无账目")


def _pack(qid: str, rows: list[dict[str, Any]], empty_text: str) -> dict[str, Any]:
    return {
        "query": {"id": qid, "empty_text": empty_text},
        "rows": rows,
        "row_count": len(rows),
        "empty": not rows,
        "partial": False,
        "errors": [],
    }


PRESETS: dict[str, Any] = {
    "q_open_overdue": _q_open_overdue,
    "q_week_health_open": _q_week_health_open,
    "q_habit_streak_break": _q_habit_streak_break,
    "q_free_slots_today": _q_free_slots_today,
    "q_finance_week_sum": _q_finance_week_sum,
}


def run_preset(db: Session, qid: str, days: int | None = None) -> dict[str, Any]:
    """执行预置查询。days=参数化范围（近 N 天）；不传=各预置默认窗。"""
    fn = PRESETS.get(qid)
    if fn is None:
        raise KeyError(qid)
    # 带 days 的预置收参；其余忽略多余参数（向前兼容）
    try:
        return fn(db, days=days)  # type: ignore[call-arg]
    except TypeError:
        return fn(db)
