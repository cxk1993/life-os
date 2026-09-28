"""日程表业务逻辑（厚，逻辑都写这里）。

★ 一次查询组装树，禁止循环里再查库（N+1 是模板黑名单）。
★ 嵌套最多 3 层（service 层校验，见 MAX_DEPTH）。
★ 父块移动/缩放时，子块跟随并自动钳制回父块边界内。
★ 空闲时段剔除已占用区间，返回 [{start, end, hours}]（AI 编排与概览都依赖它）。
"""
from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlmodel import Session, col, select

from core.config import get_settings
from core.errors import NotFoundError, ValidationError

from .models import CalendarEvent
from .schema import EventCreate, EventUpdate, FreeSlotOut

MAX_DEPTH = 3  # 父(1)/子(2)/孙(3) 合法，第 4 层拒绝


def to_local(value: datetime) -> datetime:
    """把**库内存的 UTC** 转成**主人本地时区**再出参（★ 2026-09-28 · 主人令）。

    背景：此前 API 一律回 UTC（当时的"项目规则"），人与 AI 都得先做一次心算；
    还连累出一个**用户可见的真 bug** —— `today-summary` 用字符串切片取小时
    （`str(start)[11:16]`），UTC 串切出来就是 UTC 的小时，于是**下午 3 点的课
    会显示成 "07:00"**。改为本地时区出参后，那个 bug 自动消失。

    注意：仍是**完整带偏移的 ISO8601**（如 `2026-09-28T15:00:00+08:00`），
    前端 `new Date(...)` 照旧按同一瞬间解析，**不影响前端**。
    """
    return value.astimezone(ZoneInfo(get_settings().tz))


def to_utc(value: str | datetime) -> datetime:
    """任意时间输入统一成 UTC。**必须带时区**，naive 直接报错（铁律）。"""
    if isinstance(value, str):
        # ★ query string 里的 '+' 会被解码成空格：
        #   ?start=2026-09-14T00:00:00+08:00 到达后端时是 "...00:00:00 08:00"。
        #   这里把"HH:MM(:SS) 空格 HH:MM"恢复成 "+HH:MM"，否则 fromisoformat 直接炸。
        m = re.search(r"(\d{2}:\d{2}(?::\d{2})?) (\d{2}):(\d{2})$", value)
        if m:
            value = value[: m.start()] + f"{m.group(1)}+{m.group(2)}:{m.group(3)}"
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        dt = value
    if dt.tzinfo is None:
        raise ValidationError("时间必须带时区，例如 2026-09-15T08:00:00+08:00")
    return dt.astimezone(UTC)


class CalendarService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ─────────────────────────────── 读 ───────────────────────────────
    def _dump(
        self, ev: CalendarEvent, children: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        return {
            "id": ev.id,
            "title": ev.title,
            "color": ev.color,
            "start_at": to_local(ev.start_at),
            "end_at": to_local(ev.end_at),
            "all_day": ev.all_day,
            "span_days": ev.span_days,
            "source": ev.source,
            "parent_id": ev.parent_id,
            "sort": ev.sort,
            "location": ev.location,
            "note": ev.note,
            "children": children if children is not None else [],
        }

    def _build_tree(self, rows: Sequence[CalendarEvent]) -> list[dict[str, Any]]:
        """一次查询的结果组装成树，禁止 N+1。"""
        by_id = {r.id: r for r in rows}
        children_map: dict[str, list[CalendarEvent]] = {}
        roots: list[CalendarEvent] = []
        for r in rows:
            if r.parent_id and r.parent_id in by_id:
                children_map.setdefault(r.parent_id, []).append(r)
            else:
                roots.append(r)

        def attach(node: CalendarEvent, depth: int) -> dict[str, Any]:
            kids = children_map.get(node.id, [])
            if depth < MAX_DEPTH:
                kids = sorted(kids, key=lambda x: (x.sort, x.start_at))
                child_trees = [attach(c, depth + 1) for c in kids]
            else:
                child_trees = []
            return self._dump(node, child_trees)

        roots.sort(key=lambda x: (x.start_at, x.sort))
        return [attach(r, 1) for r in roots]

    def list_range(
        self,
        frm: str | datetime,
        to: str | datetime,
        include_children: bool = True,
        flat: bool = False,
    ) -> list[dict[str, Any]]:
        start, end = to_utc(frm), to_utc(to)
        if end <= start:
            raise ValidationError("查询区间无效：to 必须晚于 from")
        rows = self.db.exec(
            select(CalendarEvent).where(
                CalendarEvent.start_at < end,
                CalendarEvent.end_at > start,
            )
        ).all()
        if flat or not include_children:
            return [self._dump(r) for r in rows]
        return self._build_tree(rows)

    def get_tree(self, event_id: str) -> dict[str, Any]:
        """取一棵完整的事件树（含全部后代）。

        ★ 一次查询组装树，禁止 N+1 —— 但**也不能只查根**：
          早期版本把 `[ev]` 单个传进 _build_tree，导致**所有树响应的 children 永远为空**
          （create/update/add_child 全走这里，实测 3 条验收因此挂掉）。
          现按层取后代：深度 ≤ MAX_DEPTH，查询次数 = 树的层数（≤3），与节点数无关。
        """
        root = self.db.get(CalendarEvent, event_id)
        if root is None:
            raise NotFoundError(f"事件不存在：{event_id}")
        rows: list[CalendarEvent] = [root]
        frontier = [root.id]
        for _ in range(MAX_DEPTH - 1):
            if not frontier:
                break
            kids = self.db.exec(
                select(CalendarEvent).where(col(CalendarEvent.parent_id).in_(frontier))
            ).all()
            rows.extend(kids)
            frontier = [k.id for k in kids]
        return self._build_tree(rows)[0]

    # ─────────────────────────────── 写 ───────────────────────────────
    def _ancestor_depth(self, ev: CalendarEvent) -> int:
        """节点深度（根=1）。"""
        depth = 1
        cur: CalendarEvent | None = ev
        while cur is not None and cur.parent_id:
            cur = self.db.get(CalendarEvent, cur.parent_id)
            depth += 1
        return depth

    def _assert_nestable(self, parent: CalendarEvent, child_depth: int = 1) -> None:
        """在 parent 下挂深度 child_depth 的子树，校验不超过 MAX_DEPTH。"""
        base = self._ancestor_depth(parent)
        if base + child_depth - 1 > MAX_DEPTH:
            raise ValidationError(f"嵌套最多 {MAX_DEPTH} 层（父链已有 {base} 层）")

    def _create_one(self, body: EventCreate, parent_id: str | None, depth: int) -> CalendarEvent:
        if depth > MAX_DEPTH:
            raise ValidationError(f"嵌套最多 {MAX_DEPTH} 层")
        start, end = to_utc(body.start_at), to_utc(body.end_at)
        if end <= start:
            raise ValidationError("end_at 必须晚于 start_at")
        # ★ 子块必须在父块内：**创建时就要钳制**，不只是父块移动时。
        #   实测 test_child_cannot_exceed_parent 抓出：子块 00:00-23:00 直接建在了
        #   09:00-12:00 的父块外 —— 卡片规则是"子块不能超出父块"。
        if parent_id is not None:
            parent = self.db.get(CalendarEvent, parent_id)
            if parent is not None:
                start, end = self._clamp_child(parent.start_at, parent.end_at, start, end)
        ev = CalendarEvent(
            title=body.title,
            color=body.color,
            start_at=start,
            end_at=end,
            all_day=body.all_day,
            parent_id=parent_id,
            span_days=body.span_days,
            source=body.source,
            sort=body.sort,
            location=body.location,
            note=body.note,
        )
        self.db.add(ev)
        self.db.flush()  # 拿到 ev.id 才能挂子块
        if body.children and depth < MAX_DEPTH:
            for c in body.children:
                self._create_one(c, parent_id=ev.id, depth=depth + 1)
        return ev

    def create(self, body: EventCreate) -> dict[str, Any]:
        parent_id = body.parent_id
        if parent_id:
            parent = self.db.get(CalendarEvent, parent_id)
            if parent is None:
                raise NotFoundError(f"父事件不存在：{parent_id}")
            self._assert_nestable(parent, child_depth=1 + (1 if body.children else 0))
        ev = self._create_one(body, parent_id=parent_id, depth=1)
        self.db.commit()
        self.db.refresh(ev)
        return self.get_tree(ev.id)

    def add_child(self, parent_id: str, body: EventCreate) -> dict[str, Any]:
        parent = self.db.get(CalendarEvent, parent_id)
        if parent is None:
            raise NotFoundError(f"父事件不存在：{parent_id}")
        self._assert_nestable(parent, child_depth=1 + (1 if body.children else 0))
        # 子块的 parent_id 强制覆盖为路径上的父
        body.parent_id = parent_id
        ev = self._create_one(body, parent_id=parent_id, depth=2)
        self.db.commit()
        self.db.refresh(ev)
        return self.get_tree(ev.id)

    @staticmethod
    def _clamp_child(
        p_start: datetime, p_end: datetime, c_start: datetime, c_end: datetime
    ) -> tuple[datetime, datetime]:
        """把子块绝对时间钳进父块边界。

        ★ 子块**比父块还长**时直接取父块（装不下就截断），而不是"保留时长"：
          保留时长的算法会把尾部推出父块外 —— 实测踩过：
          23h 的子块塞进 3h 的父块，钳完变成 [父块起点, 次日00:00]，跑出了父块。
        """
        if c_end - c_start >= p_end - p_start:
            return p_start, p_end
        dur = c_end - c_start
        if c_start >= p_end or c_end <= p_start:
            # 完全在父块之外：拉到父块起点，受父块跨度限制
            ns = p_start
            ne = min(p_start + dur, p_end)
            return ns, ne
        if c_start < p_start:
            c_start = p_start
        if c_end > p_end:
            c_start = max(p_start, p_end - dur)
            c_end = c_start + dur
        return c_start, c_end

    def _reconcile_descendants(
        self,
        parent_id: str,
        new_p_start: datetime,
        new_p_end: datetime,
        delta: timedelta,
    ) -> None:
        """父块移动/缩放后，子块跟随（同 delta）并钳制回父块内，递归到所有后代。"""
        kids = self.db.exec(
            select(CalendarEvent).where(CalendarEvent.parent_id == parent_id)
        ).all()
        for c in kids:
            cs, ce = c.start_at + delta, c.end_at + delta
            cs, ce = self._clamp_child(new_p_start, new_p_end, cs, ce)
            c.start_at, c.end_at = cs, ce
            self.db.add(c)
            self.db.flush()
            self._reconcile_descendants(c.id, cs, ce, delta)

    def update(self, event_id: str, body: EventUpdate) -> dict[str, Any]:
        ev = self.db.get(CalendarEvent, event_id)
        if ev is None:
            raise NotFoundError(f"事件不存在：{event_id}")
        old_start = ev.start_at
        if body.title is not None:
            ev.title = body.title
        if body.color is not None:
            ev.color = body.color
        if body.all_day is not None:
            ev.all_day = body.all_day
        if body.span_days is not None:
            ev.span_days = max(1, int(body.span_days))
        if body.sort is not None:
            ev.sort = body.sort
        if body.location is not None:
            ev.location = body.location
        if body.note is not None:
            ev.note = body.note
        new_start, new_end = ev.start_at, ev.end_at
        if body.start_at is not None:
            new_start = to_utc(body.start_at)
        if body.end_at is not None:
            new_end = to_utc(body.end_at)
        if new_end <= new_start:
            raise ValidationError("end_at 必须晚于 start_at")
        delta = new_start - old_start
        ev.start_at, ev.end_at = new_start, new_end
        self.db.add(ev)
        self.db.flush()
        # 父块变更后，后代跟随并钳制
        self._reconcile_descendants(ev.id, new_start, new_end, delta)
        self.db.commit()
        self.db.refresh(ev)
        return self.get_tree(ev.id)

    def update_child(self, parent_id: str, child_id: str, body: EventUpdate) -> dict[str, Any]:
        child = self._require_child(parent_id, child_id)
        if body.title is not None:
            child.title = body.title
        if body.color is not None:
            child.color = body.color
        if body.all_day is not None:
            child.all_day = body.all_day
        if body.sort is not None:
            child.sort = body.sort
        if body.location is not None:
            child.location = body.location
        if body.note is not None:
            child.note = body.note
        new_start, new_end = child.start_at, child.end_at
        if body.start_at is not None:
            new_start = to_utc(body.start_at)
        if body.end_at is not None:
            new_end = to_utc(body.end_at)
        # 子块时间不得越出父块
        parent = self.db.get(CalendarEvent, parent_id)
        assert parent is not None
        new_start, new_end = self._clamp_child(parent.start_at, parent.end_at, new_start, new_end)
        if new_end <= new_start:
            raise ValidationError("子块时长过短或越出父块边界")
        child.start_at, child.end_at = new_start, new_end
        self.db.add(child)
        self.db.commit()
        self.db.refresh(child)
        return self.get_tree(parent_id)

    def _require_child(self, parent_id: str, child_id: str) -> CalendarEvent:
        parent = self.db.get(CalendarEvent, parent_id)
        if parent is None:
            raise NotFoundError(f"父事件不存在：{parent_id}")
        child = self.db.get(CalendarEvent, child_id)
        if child is None:
            raise NotFoundError(f"子事件不存在：{child_id}")
        if child.parent_id != parent_id:
            raise ValidationError(f"子事件 {child_id} 不属于父事件 {parent_id}")
        return child

    def _delete_subtree(self, event_id: str) -> None:
        kids = self.db.exec(
            select(CalendarEvent).where(CalendarEvent.parent_id == event_id)
        ).all()
        for c in kids:
            self._delete_subtree(c.id)
        ev = self.db.get(CalendarEvent, event_id)
        if ev is not None:
            self.db.delete(ev)

    def delete(self, event_id: str) -> None:
        ev = self.db.get(CalendarEvent, event_id)
        if ev is None:
            raise NotFoundError(f"事件不存在：{event_id}")
        self._delete_subtree(event_id)
        self.db.commit()

    def delete_child(self, parent_id: str, child_id: str) -> None:
        self._require_child(parent_id, child_id)
        self._delete_subtree(child_id)
        self.db.commit()

    # ─────────────────────────── 空闲时段 ───────────────────────────
    def free_slots(self, day_start: datetime, min_hours: float = 1.0) -> list[FreeSlotOut]:
        day_end = day_start + timedelta(days=1) - timedelta(seconds=1)
        rows = self.db.exec(
            select(CalendarEvent).where(
                CalendarEvent.start_at < day_end,
                CalendarEvent.end_at > day_start,
                col(CalendarEvent.parent_id).is_(None),
            )
        ).all()
        busy = sorted(
            [(max(r.start_at, day_start), min(r.end_at, day_end)) for r in rows],
            key=lambda x: x[0],
        )
        # 合并重叠/相邻占用
        merged: list[tuple[datetime, datetime]] = []
        for s, e in busy:
            if merged and s <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], e))
            else:
                merged.append((s, e))

        slots: list[FreeSlotOut] = []
        cursor = day_start
        for s, e in merged:
            if (s - cursor).total_seconds() / 3600 >= min_hours:
                slots.append(self._mk_slot(cursor, s))
            cursor = max(cursor, e)
        if (day_end - cursor).total_seconds() / 3600 >= min_hours:
            slots.append(self._mk_slot(cursor, day_end))
        return slots

    @staticmethod
    def _mk_slot(start: datetime, end: datetime) -> FreeSlotOut:
        return FreeSlotOut(
            start=to_local(start),
            end=to_local(end),
            hours=round((end - start).total_seconds() / 3600, 2),
        )
