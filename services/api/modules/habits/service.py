"""习惯打卡业务逻辑。

★ 打卡日期是本地日历日（Asia/Shanghai），数据库存 date，不存时刻。
★ streak：连续打卡天数；休息日（rest_weekdays / is_rest）跳过且不破连击。
★ 一次查询拿齐 log，禁止在循环里查库。
★ 事件在本层 publish，内核 SSE 自动下推。
"""
from __future__ import annotations

import json
from datetime import date as DateType
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlmodel import Session, col, select

from core.errors import NotFoundError, ValidationError
from core.events import event_bus

from .models import RULE_CUSTOM, RULE_DAILY, RULE_WEEKLY, Habit, HabitLog
from .schema import CheckIn, HabitCreate, HabitUpdate, SummaryOut

SH_TZ = ZoneInfo("Asia/Shanghai")
_VALID_WEEKDAYS = set(range(7))


def local_today() -> DateType:
    return datetime.now(SH_TZ).date()


def _parse_rule(raw: str) -> dict[str, Any]:
    try:
        val = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {"type": RULE_DAILY}
    if not isinstance(val, dict):
        return {"type": RULE_DAILY}
    t = str(val.get("type") or RULE_DAILY)
    if t not in (RULE_DAILY, RULE_WEEKLY, RULE_CUSTOM):
        t = RULE_DAILY
    out: dict[str, Any] = {"type": t}
    if t == RULE_WEEKLY:
        out["times"] = max(1, min(7, int(val.get("times") or 3)))
    if t == RULE_CUSTOM:
        days = val.get("days") or []
        out["days"] = sorted({int(d) for d in days if int(d) in _VALID_WEEKDAYS})
    return out


def _parse_weekdays(raw: str) -> list[int]:
    if not raw:
        return []
    out: list[int] = []
    for p in raw.split(","):
        p = p.strip()
        if p.isdigit() and int(p) in _VALID_WEEKDAYS:
            out.append(int(p))
    return sorted(set(out))


def _dump_weekdays(days: list[int]) -> str:
    return ",".join(str(d) for d in sorted(set(days) if days else []))


class HabitsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ───────────────────────── 读 ─────────────────────────
    def _dump(
        self,
        h: Habit,
        *,
        today_status: str = "pending",
        streak: int = 0,
    ) -> dict[str, Any]:
        return {
            "id": h.id,
            "name": h.name,
            "target": h.target,
            "rule": _parse_rule(h.rule),
            "color": h.color,
            "reminder_time": h.reminder_time,
            "rest_weekdays": _parse_weekdays(h.rest_weekdays),
            "archived": h.archived,
            "sort": h.sort,
            "today_status": today_status,
            "streak": streak,
            "created_at": h.created_at,
            "updated_at": h.updated_at,
        }

    def _dump_log(self, log: HabitLog) -> dict[str, Any]:
        return {
            "id": log.id,
            "habit_id": log.habit_id,
            "date": log.date,
            "value": log.value,
            "note": log.note,
            "is_rest": log.is_rest,
            "created_at": log.created_at,
        }

    def _logs_for(self, habit_id: str) -> list[HabitLog]:
        return list(
            self.db.exec(
                select(HabitLog).where(HabitLog.habit_id == habit_id)
            ).all()
        )

    def _is_rest_day(self, h: Habit, d: DateType) -> bool:
        return d.weekday() in _parse_weekdays(h.rest_weekdays)

    def _today_status(self, h: Habit, logs: list[HabitLog], today: DateType) -> str:
        if self._is_rest_day(h, today):
            return "rest"
        for log in logs:
            if log.date == today:
                return "rest" if log.is_rest else "done"
        return "pending"

    def _streak(self, h: Habit, logs: list[HabitLog], today: DateType) -> int:
        """连续打卡天数。休息日跳过；请假(is_rest)也跳过且不断连。"""
        done_dates = {log.date for log in logs if not log.is_rest}
        rest_flags = {log.date for log in logs if log.is_rest}
        rest_weekdays = set(_parse_weekdays(h.rest_weekdays))
        # 若今天还没打卡，从昨天起算（今天 pending 不清零）
        cursor = today if today in done_dates else today - timedelta(days=1)
        streak = 0
        guard = 0
        while guard < 400:
            guard += 1
            if cursor.weekday() in rest_weekdays or cursor in rest_flags:
                cursor -= timedelta(days=1)
                continue
            if cursor in done_dates:
                streak += 1
                cursor -= timedelta(days=1)
                continue
            break
        return streak

    def list_habits(self, include_archived: bool = False) -> list[dict[str, Any]]:
        stmt = select(Habit)
        if not include_archived:
            stmt = stmt.where(Habit.archived == False)  # noqa: E712
        rows = list(self.db.exec(stmt).all())
        today = local_today()
        # 一次查全部 log（习惯数量很小），避免 N+1
        all_logs = list(self.db.exec(select(HabitLog)).all())
        by_habit: dict[str, list[HabitLog]] = {}
        for log in all_logs:
            by_habit.setdefault(log.habit_id, []).append(log)
        rows.sort(key=lambda h: (h.sort, h.name))
        return [
            self._dump(
                h,
                today_status=self._today_status(h, by_habit.get(h.id, []), today),
                streak=self._streak(h, by_habit.get(h.id, []), today),
            )
            for h in rows
        ]

    def get(self, habit_id: str) -> dict[str, Any]:
        h = self.db.get(Habit, habit_id)
        if h is None:
            raise NotFoundError(f"习惯不存在：{habit_id}")
        logs = self._logs_for(habit_id)
        today = local_today()
        return self._dump(
            h,
            today_status=self._today_status(h, logs, today),
            streak=self._streak(h, logs, today),
        )

    def list_logs(
        self, habit_id: str, frm: DateType | None = None, to: DateType | None = None
    ) -> list[dict[str, Any]]:
        h = self.db.get(Habit, habit_id)
        if h is None:
            raise NotFoundError(f"习惯不存在：{habit_id}")
        stmt = select(HabitLog).where(HabitLog.habit_id == habit_id)
        if frm is not None:
            stmt = stmt.where(col(HabitLog.date) >= frm)
        if to is not None:
            stmt = stmt.where(col(HabitLog.date) <= to)
        rows = list(self.db.exec(stmt).all())
        rows.sort(key=lambda r: r.date)
        return [self._dump_log(r) for r in rows]

    def summary(self) -> SummaryOut:
        habits = [
            h for h in self.db.exec(select(Habit).where(Habit.archived == False)).all()  # noqa: E712
        ]
        today = local_today()
        all_logs = list(self.db.exec(select(HabitLog)).all())
        by_habit: dict[str, list[HabitLog]] = {}
        for log in all_logs:
            by_habit.setdefault(log.habit_id, []).append(log)
        done = pending = rest = 0
        best = 0
        for h in habits:
            logs = by_habit.get(h.id, [])
            status = self._today_status(h, logs, today)
            if status == "done":
                done += 1
            elif status == "rest":
                rest += 1
            else:
                pending += 1
            best = max(best, self._streak(h, logs, today))
        return SummaryOut(
            total=len(habits), done=done, pending=pending, rest=rest, best_streak=best
        )

    # ───────────────────────── 写 ─────────────────────────
    def _validate_rule(self, rule: dict[str, Any]) -> dict[str, Any]:
        t = rule.get("type")
        if t == RULE_WEEKLY and not rule.get("times"):
            rule["times"] = 3
        if t == RULE_CUSTOM:
            days = rule.get("days") or []
            if not days:
                raise ValidationError("custom 规则必须指定 days（0=周一 … 6=周日）")
        return rule

    def create(self, body: HabitCreate) -> dict[str, Any]:
        name = body.name.strip()
        if not name:
            raise ValidationError("name 不能为空")
        for d in body.rest_weekdays:
            if d not in _VALID_WEEKDAYS:
                raise ValidationError(f"rest_weekdays 越界：{d}（合法 0–6）")
        rule = self._validate_rule(_parse_rule(body.rule.model_dump_json()))
        h = Habit(
            name=name,
            target=body.target,
            rule=json.dumps(rule, ensure_ascii=False),
            color=body.color,
            reminder_time=body.reminder_time,
            rest_weekdays=_dump_weekdays(body.rest_weekdays),
            sort=body.sort,
        )
        self.db.add(h)
        self.db.commit()
        self.db.refresh(h)
        out = self._dump(h)
        event_bus.publish("habits.habit.created", out, source="habits")
        return out

    def update(self, habit_id: str, body: HabitUpdate) -> dict[str, Any]:
        h = self.db.get(Habit, habit_id)
        if h is None:
            raise NotFoundError(f"习惯不存在：{habit_id}")
        if body.name is not None:
            name = body.name.strip()
            if not name:
                raise ValidationError("name 不能为空")
            h.name = name
        if body.target is not None:
            h.target = body.target
        if body.rule is not None:
            rule = self._validate_rule(_parse_rule(body.rule.model_dump_json()))
            h.rule = json.dumps(rule, ensure_ascii=False)
        if body.color is not None:
            h.color = body.color
        if body.reminder_time is not None:
            h.reminder_time = body.reminder_time
        if body.rest_weekdays is not None:
            for d in body.rest_weekdays:
                if d not in _VALID_WEEKDAYS:
                    raise ValidationError(f"rest_weekdays 越界：{d}（合法 0–6）")
            h.rest_weekdays = _dump_weekdays(body.rest_weekdays)
        if body.archived is not None:
            h.archived = body.archived
        if body.sort is not None:
            h.sort = body.sort
        self.db.add(h)
        self.db.commit()
        self.db.refresh(h)
        out = self.get(habit_id)
        event_bus.publish("habits.habit.updated", out, source="habits")
        return out

    def delete(self, habit_id: str) -> None:
        h = self.db.get(Habit, habit_id)
        if h is None:
            raise NotFoundError(f"习惯不存在：{habit_id}")
        for log in self._logs_for(habit_id):
            self.db.delete(log)
        # 先冲掉 log 的 DELETE，再删习惯，否则 SQLite 外键会拦
        self.db.flush()
        self.db.delete(h)
        self.db.commit()
        event_bus.publish("habits.habit.deleted", {"id": habit_id}, source="habits")

    def checkin(self, habit_id: str, body: CheckIn) -> dict[str, Any]:
        h = self.db.get(Habit, habit_id)
        if h is None:
            raise NotFoundError(f"习惯不存在：{habit_id}")
        d = body.date or local_today()
        existing = self.db.exec(
            select(HabitLog).where(
                HabitLog.habit_id == habit_id, HabitLog.date == d
            )
        ).first()
        if existing is not None:
            existing.value = body.value
            existing.note = body.note
            existing.is_rest = body.is_rest
            self.db.add(existing)
            self.db.commit()
            self.db.refresh(existing)
            log = existing
        else:
            log = HabitLog(
                habit_id=habit_id,
                date=d,
                value=body.value,
                note=body.note,
                is_rest=body.is_rest,
            )
            self.db.add(log)
            self.db.commit()
            self.db.refresh(log)
        out = self.get(habit_id)
        event_bus.publish("habits.log.checked", {"habit": out, "log": self._dump_log(log)},
                          source="habits")
        return out

    def uncheck(self, habit_id: str, day: DateType) -> dict[str, Any]:
        h = self.db.get(Habit, habit_id)
        if h is None:
            raise NotFoundError(f"习惯不存在：{habit_id}")
        log = self.db.exec(
            select(HabitLog).where(
                HabitLog.habit_id == habit_id, HabitLog.date == day
            )
        ).first()
        if log is not None:
            self.db.delete(log)
            self.db.commit()
        out = self.get(habit_id)
        event_bus.publish("habits.log.unchecked", {"habit": out, "date": day},
                          source="habits")
        return out
