"""理财业务逻辑：流水 CRUD + 过滤列表 + 区间汇总。

★ 金额用整数分；Decimal 字符串入参在此换算，禁止浮点累加。
★ 时间输入必须带时区，naive 直接 ValidationError（项目铁律）。
★ 可空列比较用 col()（mypy/sqlalchemy 类型友好）。
★ 事件在本层 publish，内核 SSE 自动下推。
"""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlmodel import Session, col, select

from core.errors import NotFoundError, ValidationError
from core.events import event_bus

from .models import DIR_EXPENSE, DIR_INCOME, FinanceEntry
from .schema import (
    CategoryTotal,
    FinanceEntryCreate,
    FinanceEntryUpdate,
    FinanceSummaryOut,
)


def to_utc(value: str | datetime) -> datetime:
    """任意时间输入统一成 UTC。必须带时区，naive 直接报错。

    容错：查询串裸传 `+08:00` 时 `+` 可能被解码成空格，这里还原一次。
    """
    if not isinstance(value, str):
        dt = value
    else:
        s = value.strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            fixed = s
            t_idx = s.find("T")
            if t_idx >= 0:
                sp = s.rfind(" ")
                if sp > t_idx:
                    fixed = s[:sp] + "+" + s[sp + 1 :]
            try:
                dt = datetime.fromisoformat(fixed)
            except ValueError as e:
                raise ValidationError(f"时间格式非法：{value}") from e
    if dt.tzinfo is None:
        raise ValidationError("时间必须带时区，例如 2026-09-15T08:00:00+08:00")
    return dt.astimezone(UTC)


def amount_to_cents(amount_cents: int | None, amount: str | None) -> int:
    """金额入参 → 整数分。amount_cents 优先；amount 为 Decimal 字符串。"""
    if amount_cents is not None:
        if amount_cents < 1:
            raise ValidationError("金额必须为正（分）")
        return int(amount_cents)
    if amount is None or not str(amount).strip():
        raise ValidationError("需要 amount_cents（整数分）或 amount（Decimal 字符串）")
    try:
        d = Decimal(str(amount).strip())
    except (InvalidOperation, ValueError) as e:
        raise ValidationError(f"金额格式非法：{amount}") from e
    if d <= 0:
        raise ValidationError("金额必须为正")
    scaled = d * 100
    if scaled != scaled.to_integral_value():
        raise ValidationError("金额最多两位小数（分）")
    cents = int(scaled)
    if cents < 1:
        raise ValidationError("金额必须为正（分）")
    return cents


class FinanceService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ───────────────────────── 序列化 ─────────────────────────
    def _dump(self, r: FinanceEntry) -> dict[str, Any]:
        return {
            "id": r.id,
            "amount_cents": r.amount_cents,
            "direction": r.direction,
            "category": r.category or "",
            "account": r.account or "",
            "occurred_at": r.occurred_at,
            "note": r.note,
            "created_at": r.created_at,
            "updated_at": r.updated_at,
        }

    # ───────────────────────── 读 ─────────────────────────
    def list_entries(
        self,
        *,
        category: str | None = None,
        account: str | None = None,
        direction: str | None = None,
        date_from: str | datetime | None = None,
        date_to: str | datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        stmt = select(FinanceEntry)
        if category is not None:
            stmt = stmt.where(FinanceEntry.category == category)
        if account is not None:
            stmt = stmt.where(FinanceEntry.account == account)
        if direction is not None:
            if direction not in (DIR_EXPENSE, DIR_INCOME):
                raise ValidationError("direction 只能是 expense 或 income")
            stmt = stmt.where(FinanceEntry.direction == direction)
        if date_from is not None:
            stmt = stmt.where(col(FinanceEntry.occurred_at) >= to_utc(date_from))
        if date_to is not None:
            stmt = stmt.where(col(FinanceEntry.occurred_at) <= to_utc(date_to))

        rows_all = list(self.db.exec(stmt).all())
        # 时间倒序，新流水在前
        rows_all.sort(key=lambda r: (r.occurred_at, r.created_at), reverse=True)
        total = len(rows_all)
        page = rows_all[offset : offset + limit]
        return {
            "items": [self._dump(r) for r in page],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    def get(self, id_: str) -> dict[str, Any]:
        r = self.db.get(FinanceEntry, id_)
        if r is None:
            raise NotFoundError(f"流水不存在：{id_}")
        return self._dump(r)

    def summary(
        self,
        *,
        date_from: str | datetime | None = None,
        date_to: str | datetime | None = None,
    ) -> FinanceSummaryOut:
        stmt = select(FinanceEntry)
        if date_from is not None:
            stmt = stmt.where(col(FinanceEntry.occurred_at) >= to_utc(date_from))
        if date_to is not None:
            stmt = stmt.where(col(FinanceEntry.occurred_at) <= to_utc(date_to))
        rows = list(self.db.exec(stmt).all())

        expense = 0
        income = 0
        by_cat: dict[str, CategoryTotal] = {}
        for r in rows:
            cat = r.category or ""
            bucket = by_cat.get(cat)
            if bucket is None:
                bucket = CategoryTotal(category=cat)
                by_cat[cat] = bucket
            bucket.count += 1
            if r.direction == DIR_INCOME:
                income += r.amount_cents
                bucket.income_cents += r.amount_cents
            else:
                expense += r.amount_cents
                bucket.expense_cents += r.amount_cents

        cats = sorted(
            by_cat.values(),
            key=lambda c: (-(c.expense_cents + c.income_cents), c.category),
        )
        df = to_utc(date_from) if date_from is not None else None
        dt = to_utc(date_to) if date_to is not None else None
        return FinanceSummaryOut(
            date_from=df,
            date_to=dt,
            expense_cents=expense,
            income_cents=income,
            net_cents=income - expense,
            count=len(rows),
            by_category=cats,
        )

    # ───────────────────────── 写 ─────────────────────────
    def create(self, body: FinanceEntryCreate) -> dict[str, Any]:
        cents = amount_to_cents(body.amount_cents, body.amount)
        note = body.note.strip() if body.note else None
        if note == "":
            note = None
        item = FinanceEntry(
            amount_cents=cents,
            direction=body.direction,
            category=(body.category or "").strip(),
            account=(body.account or "").strip(),
            occurred_at=to_utc(body.occurred_at),
            note=note,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        event_bus.publish("finance.entry.created", self._dump(item), source="finance")
        return self._dump(item)

    def update(self, id_: str, body: FinanceEntryUpdate) -> dict[str, Any]:
        item = self.db.get(FinanceEntry, id_)
        if item is None:
            raise NotFoundError(f"流水不存在：{id_}")
        if body.direction is not None:
            item.direction = body.direction
        if body.amount_cents is not None or body.amount is not None:
            item.amount_cents = amount_to_cents(body.amount_cents, body.amount)
        if body.category is not None:
            item.category = body.category.strip()
        if body.account is not None:
            item.account = body.account.strip()
        if body.occurred_at is not None:
            item.occurred_at = to_utc(body.occurred_at)
        if "note" in body.model_fields_set:
            note = body.note.strip() if body.note else None
            item.note = note if note else None
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        event_bus.publish("finance.entry.updated", self._dump(item), source="finance")
        return self._dump(item)

    def delete(self, id_: str) -> None:
        item = self.db.get(FinanceEntry, id_)
        if item is None:
            raise NotFoundError(f"流水不存在：{id_}")
        payload = self._dump(item)
        self.db.delete(item)
        self.db.commit()
        event_bus.publish("finance.entry.deleted", payload, source="finance")
