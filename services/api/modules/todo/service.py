"""todo 业务逻辑：CRUD + 完成/取消 + 周期生成 + 导入/导出 + 概览统计。

★ 复用 T04 的 db/todo_parser.py（parse_todo_line / to_todo_line），不许重写解析器。
★ 快速添加语法糖（@自然语言日期 / !高|中|低 / #标签 / 🔁规则）在此解析。
★ 周期任务：完成时写 done_at，并按 recur_rule（RRULE）生成下一条独立实例，
  原始记录保留（series_id 串起整条链，instance_no 递增）。
"""
from __future__ import annotations

import re
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlmodel import Session, col, select

from core.errors import NotFoundError, ValidationError
from core.events import event_bus
from db.base import utcnow
from db.repo import decode_cursor, encode_cursor
from db.todo_parser import TodoLine, parse_todo_line, to_todo_line

from .models import TodoItem, tags_from_json, tags_to_json
from .schema import (
    SummaryOut,
    TodoCreate,
    TodoUpdate,
    ToggleOut,
)

# 主人时区（Asia/Shanghai，无夏令时）→ 直接用固定 UTC+8，避免 tzdata 依赖。
SH_TZ = ZoneInfo("Asia/Shanghai")
UTC = UTC

PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2, None: 3}
_WEEKDAY = {"周一": 0, "周二": 1, "周三": 2, "周四": 3, "周五": 4, "周六": 5, "周日": 6,
            "星期日": 6, "星期天": 6}


# ───────────────────────── 时间工具 ─────────────────────────
def to_utc(value: str | datetime) -> datetime:
    """任意时间输入统一成 UTC。必须带时区，naive 直接报错（铁律）。"""
    dt = (
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        if isinstance(value, str)
        else value
    )
    if dt.tzinfo is None:
        raise ValidationError("时间必须带时区，例如 2026-09-15T08:00:00+08:00")
    return dt.astimezone(UTC)


def date_to_utc(d: date) -> datetime:
    """date（无时分）→ 当天上海 0 点（UTC）。用于只有日期的截止。"""
    return datetime(d.year, d.month, d.day, tzinfo=SH_TZ).astimezone(UTC)


def parse_natural_date(token: str, base: date | None = None) -> date | None:
    """自然语言日期 → date。今天/明天/后天/周X/10-01/M-D（≤30 行，无第三方库）。"""
    base = base or date.today()
    t = token.strip()
    if t in ("今天", "today"):
        return base
    if t in ("明天", "tomorrow"):
        return base + timedelta(days=1)
    if t in ("后天",):
        return base + timedelta(days=2)
    if t in _WEEKDAY:
        delta = (_WEEKDAY[t] - base.weekday()) % 7
        return base + timedelta(days=delta or 7)
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})|(\d{1,2})[-/](\d{1,2})", t)
    if m:
        if m.group(1):
            y, mo, da = int(m.group(1)), int(m.group(2)), int(m.group(3))
        else:
            y, mo, da = base.year, int(m.group(4)), int(m.group(5))
        try:
            return date(y, mo, da)
        except ValueError:
            return None
    return None


def parse_quick_line(raw: str) -> TodoLine:
    """快速添加语法糖解析：!优先级 / @自然语言日期 / #标签 / 🔁规则。"""
    line = raw.strip()
    if not line.startswith("- ["):
        line = "- [ ] " + line
    priority = None
    m = re.search(r"!(高|中|低)\b", line)
    if m:
        priority = {"高": "high", "中": "medium", "低": "low"}[m.group(1)]
        line = line[: m.start()] + line[m.end():]
    # @自然语言日期（不带括号）→ 转成 @(YYYY-MM-DD) 让 parse_todo_line 接管

    def repl(dm: re.Match[str]) -> str:
        tok = dm.group(1)
        # parse_todo_line 只认带括号的 `(@YYYY-MM-DD)` 形式。
        # ISO 日期也要补括号——否则 @2026-09-21 会原样留在正文里（实测踩过）。
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", tok):
            return f"(@{tok})"
        d = parse_natural_date(tok)
        return f"(@{d.isoformat()})" if d else dm.group(0)

    line = re.sub(r"@([^\s(@]+)", repl, line)
    tl = parse_todo_line(line)
    if priority:
        tl.priority = priority
    return tl


def next_occurrence(rule: str, after: datetime) -> datetime | None:
    """按 RRULE 算下一次触发时间（UTC）。识别不了返回 None。"""
    parts = {k.upper(): v for k, v in (p.split("=", 1) for p in rule.split(";") if "=" in p)}
    freq = parts.get("FREQ")
    interval = int(parts.get("INTERVAL", "1") or 1)
    base = after.astimezone(SH_TZ)
    if freq == "DAILY":
        nd = base + timedelta(days=interval)
    elif freq == "WEEKLY":
        byday = parts.get("BYDAY", "MO")[:2].upper()
        wd = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}.get(byday, 0)
        days = ((wd - base.weekday()) % 7) or 7
        nd = base + timedelta(days=days)
    elif freq == "MONTHLY":
        y, mo = base.year, base.month + interval
        while mo > 12:
            mo -= 12
            y += 1
        dim = [31, 29 if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else 28,
               31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mo - 1]
        nd = base.replace(year=y, month=mo, day=min(base.day, dim))
    elif freq == "YEARLY":
        try:
            nd = base.replace(year=base.year + interval)
        except ValueError:
            nd = base.replace(year=base.year + interval, month=2, day=28)
    else:
        return None
    return nd.astimezone(UTC)


class TodoService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ───────────────────────── 序列化 ─────────────────────────
    def _dump(self, r: TodoItem) -> dict:
        return {
            "id": r.id, "text": r.text, "done": r.done,
            "done_at": r.done_at, "due_at": r.due_at,
            "priority": r.priority, "recur_rule": r.recur_rule,
            "tags": tags_from_json(r.tags), "source_path": r.source_path,
            "source_line": r.source_line, "sort": r.sort,
            "series_id": r.series_id, "instance_no": r.instance_no,
            "created_at": r.created_at, "updated_at": r.updated_at,
        }

    def _sort_key(self, r: TodoItem) -> tuple[int, int, datetime, int, str]:
        undone = not r.done
        overdue = undone and r.due_at is not None and r.due_at < utcnow()
        due = r.due_at or datetime.max.replace(tzinfo=UTC)
        return (0 if overdue else (1 if undone else 2), PRIORITY_RANK.get(r.priority, 3), due,
                r.sort, r.text or "")

    # ───────────────────────── 读 ─────────────────────────
    def list_items(
        self,
        status: str | None = None,
        due_before: str | None = None,
        due_after: str | None = None,
        tag: str | None = None,
        source: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        stmt = select(TodoItem)
        conds: list[Any] = []
        if status == "done":
            conds.append(TodoItem.done == True)  # noqa: E712
        elif status == "todo":
            conds.append(TodoItem.done == False)  # noqa: E712
        if due_before:
            conds.append(col(TodoItem.due_at) <= to_utc(due_before))
        if due_after:
            conds.append(col(TodoItem.due_at) >= to_utc(due_after))
        if source:
            conds.append(TodoItem.source_path == source)
        for c in conds:
            stmt = stmt.where(c)
        rows: list[TodoItem] = list(self.db.exec(stmt).all())
        if tag:
            rows = [r for r in rows if tag in tags_from_json(r.tags)]
        rows.sort(key=self._sort_key)
        offset = decode_cursor(cursor) if cursor else 0
        page = rows[offset: offset + limit]
        next_cursor = encode_cursor(offset + limit) if offset + limit < len(rows) else None
        return [self._dump(r) for r in page], next_cursor

    def get(self, id_: str) -> dict:
        r = self.db.get(TodoItem, id_)
        if r is None:
            raise NotFoundError(f"待办不存在：{id_}")
        return self._dump(r)

    def summary(self) -> SummaryOut:
        now = datetime.now(SH_TZ)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=today_start.weekday())
        week_end = week_start + timedelta(days=7)
        rows = self.db.exec(select(TodoItem)).all()
        today = sum(1 for r in rows if (not r.done) and r.due_at
                    and r.due_at.astimezone(SH_TZ).date() == now.date())
        overdue = sum(1 for r in rows if (not r.done) and r.due_at
                      and r.due_at.astimezone(SH_TZ).date() < now.date())
        week_done = sum(1 for r in rows if r.done and r.done_at
                        and week_start <= r.done_at.astimezone(SH_TZ) < week_end)
        return SummaryOut(today=today, overdue=overdue, week_done=week_done)

    def today_summary(self) -> dict[str, Any]:
        """U2 今日摘要（today-summary 规范 v1：{title, items<=5:[{text,state,count?}], link}）。

        今日到期 + 逾期未完成 -> items（逾期 state=alert、今日到期 state=due）；
        今日已完成数 -> done（顶层扩展，视图层可展示）。
        """
        now = datetime.now(SH_TZ)
        day = now.date()
        day_start = datetime.combine(day, time.min, tzinfo=SH_TZ)
        day_end = day_start + timedelta(days=1)
        rows = self.db.exec(select(TodoItem)).all()
        due: list[tuple[datetime, TodoItem]] = []
        for r in rows:
            if r.done or not r.due_at:
                continue
            due_d = r.due_at.astimezone(SH_TZ)
            if due_d.date() == day or due_d < day_start:
                due.append((due_d, r))
        due.sort(key=lambda x: x[0])
        done_today = sum(
            1
            for r in rows
            if r.done
            and r.done_at
            and r.done_at.astimezone(SH_TZ).date() == day
        )
        items = [
            {
                "text": r.text,
                "state": "alert" if due_d < day_start else "due",
                "count": 1,
            }
            for due_d, r in due[:5]
        ]
        return {
            "title": f"今日待办 {len(due)} 项",
            "items": items,
            "done": done_today,
            "link": "/todo",
        }

    # ───────────────────────── 写 ─────────────────────────
    def create(self, body: TodoCreate) -> dict:
        if body.raw is not None and body.raw.strip():
            tl = parse_quick_line(body.raw)
            item = TodoItem(
                text=tl.text, done=tl.done,
                due_at=date_to_utc(tl.due_at) if tl.due_at else None,
                priority=tl.priority, recur_rule=tl.recur_rule,
                tags=tags_to_json(tl.tags),
            )
        else:
            if not body.text or not body.text.strip():
                raise ValidationError("text 不能为空")
            item = TodoItem(
                text=body.text.strip(),
                due_at=to_utc(body.due_at) if body.due_at else None,
                priority=body.priority, recur_rule=body.recur_rule,
                tags=tags_to_json(body.tags),
            )
        item.series_id = item.id  # 单条自成链
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        event_bus.publish("todo.item.created", self._dump(item), source="todo")
        return self._dump(item)

    def update(self, id_: str, body: TodoUpdate) -> dict:
        item = self.db.get(TodoItem, id_)
        if item is None:
            raise NotFoundError(f"待办不存在：{id_}")
        if body.text is not None:
            item.text = body.text
        if body.done is not None and body.done != item.done:
            item.done = body.done
            item.done_at = utcnow() if body.done else None
        if "due_at" in body.model_fields_set:
            item.due_at = to_utc(body.due_at) if body.due_at else None
        if body.priority is not None:
            item.priority = body.priority
        if body.recur_rule is not None:
            item.recur_rule = body.recur_rule
        if body.tags is not None:
            item.tags = tags_to_json(body.tags)
        if body.sort is not None:
            item.sort = body.sort
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        event_bus.publish("todo.item.updated", self._dump(item), source="todo")
        return self._dump(item)

    def delete(self, id_: str) -> None:
        item = self.db.get(TodoItem, id_)
        if item is None:
            raise NotFoundError(f"待办不存在：{id_}")
        self.db.delete(item)
        self.db.commit()

    def _spawn_next(self, item: TodoItem) -> TodoItem | None:
        if not item.due_at or not item.recur_rule:
            return None
        nxt = next_occurrence(item.recur_rule, item.due_at)
        if nxt is None:
            return None
        child = TodoItem(
            text=item.text, done=False, due_at=nxt, priority=item.priority,
            recur_rule=item.recur_rule, tags=item.tags, source_path=item.source_path,
            series_id=item.series_id, instance_no=item.instance_no + 1,
        )
        self.db.add(child)
        self.db.commit()
        self.db.refresh(child)
        event_bus.publish("todo.item.created", self._dump(child), source="todo")
        return child

    def toggle(self, id_: str) -> ToggleOut:
        item = self.db.get(TodoItem, id_)
        if item is None:
            raise NotFoundError(f"待办不存在：{id_}")
        if not item.done:
            item.done = True
            item.done_at = utcnow()
            self.db.add(item)
            self.db.commit()
            self.db.refresh(item)
            nxt = self._spawn_next(item) if item.recur_rule else None
            event_bus.publish("todo.item.completed", self._dump(item), source="todo")
            return ToggleOut(
                id=item.id, done=True, done_at=item.done_at,
                next_id=nxt.id if nxt else None,
                next_due_at=nxt.due_at if nxt else None,
            )
        item.done = False
        item.done_at = None
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        event_bus.publish("todo.item.updated", self._dump(item), source="todo")
        return ToggleOut(id=item.id, done=False, done_at=None)

    # ───────────────────────── 导入 / 导出 ─────────────────────────
    def import_markdown(
        self, content: str, source_path: str | None = None
    ) -> tuple[int, int, list[dict[str, Any]]]:
        items: list[TodoItem] = []
        task_lines = 0
        for i, line in enumerate(content.splitlines(), 1):
            s = line.strip()
            if not s.startswith("- ["):
                continue
            task_lines += 1
            try:
                tl = parse_todo_line(s)
            except ValueError:
                continue
            item = TodoItem(
                text=tl.text, done=tl.done,
                due_at=date_to_utc(tl.due_at) if tl.due_at else None,
                priority=tl.priority, recur_rule=tl.recur_rule,
                tags=tags_to_json(tl.tags), source_path=source_path, source_line=i,
            )
            item.series_id = item.id
            self.db.add(item)
            items.append(item)
        self.db.commit()
        for it in items:
            self.db.refresh(it)
            event_bus.publish("todo.item.created", self._dump(it), source="todo")
        return len(items), task_lines, [self._dump(it) for it in items]

    def export_markdown(self, status: str | None = None, tag: str | None = None) -> str:
        rows: list[TodoItem] = list(self.db.exec(select(TodoItem)).all())
        if status == "done":
            rows = [r for r in rows if r.done]
        elif status == "todo":
            rows = [r for r in rows if not r.done]
        if tag:
            rows = [r for r in rows if tag in tags_from_json(r.tags)]
        rows.sort(key=lambda r: (r.source_path or "", r.source_line or 0, r.created_at))
        lines = []
        for r in rows:
            d = r.due_at.astimezone(SH_TZ).date() if r.due_at else None
            tl = TodoLine(done=r.done, text=r.text, due_at=d, priority=r.priority,
                         recur_rule=r.recur_rule, tags=tags_from_json(r.tags))
            lines.append(to_todo_line(tl))
        return "\n".join(lines) + ("\n" if lines else "")
