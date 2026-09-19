"""健康业务逻辑（T21）。

★ followup_needed=true 时 publish health.care.requested（带 idempotency_key）。
★ 绝不 import todo、绝不 join 其表（ADR-0002）。
★ 时间入参必须带时区。
"""
from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlmodel import Session, col, select

from core.errors import NotFoundError, ValidationError
from core.events import event_bus

from .models import KINDS, HealthRecord
from .schema import HealthRecordCreate, HealthRecordUpdate

EVENT_CARE = "health.care.requested"


def to_utc(value: str | datetime) -> datetime:
    if not isinstance(value, str):
        dt = value
    else:
        s = value.strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(s)
        except ValueError as e:
            raise ValidationError(f"时间格式非法：{value}") from e
    if dt.tzinfo is None:
        raise ValidationError("时间必须带时区，例如 2026-09-20T08:00:00+08:00")
    return dt.astimezone(UTC)


def _due_str(due: date | None) -> str | None:
    return due.isoformat() if due else None


def care_idempotency_key(record_id: str, due: date | None) -> str:
    return f"health-followup:{record_id}:{_due_str(due) or 'none'}"


def dump_record(r: HealthRecord) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "kind": r.kind,
        "title": r.title,
        "occurred_at": r.occurred_at,
        "severity": r.severity,
        "note": r.note,
        "followup_needed": r.followup_needed,
        "followup_due": r.followup_due,
        "created_at": getattr(r, "created_at", None),
        "updated_at": getattr(r, "updated_at", None),
    }


def publish_care_requested(rec: HealthRecord) -> str:
    """发布跟进请求；返回 idempotency_key。消费方（todo）自行订阅。"""
    key = care_idempotency_key(str(rec.id), rec.followup_due)
    event_bus.publish(
        EVENT_CARE,
        payload={
            "record_id": str(rec.id),
            "kind": rec.kind,
            "title": rec.title,
            "suggest_due": _due_str(rec.followup_due),
            "source": "health",
            "idempotency_key": key,
        },
        source="health",
    )
    return key


class HealthService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_records(
        self,
        *,
        kind: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        followup_only: bool = False,
    ) -> list[dict[str, Any]]:
        stmt = select(HealthRecord)
        if kind:
            if kind not in KINDS:
                raise ValidationError(f"kind 非法：{kind}")
            stmt = stmt.where(col(HealthRecord.kind) == kind)
        if followup_only:
            stmt = stmt.where(col(HealthRecord.followup_needed) == True)  # noqa: E712
        if date_from:
            stmt = stmt.where(col(HealthRecord.occurred_at) >= to_utc(date_from))
        if date_to:
            stmt = stmt.where(col(HealthRecord.occurred_at) <= to_utc(date_to))
        stmt = stmt.order_by(col(HealthRecord.occurred_at).desc())
        return [dump_record(r) for r in self.db.exec(stmt).all()]

    def get(self, record_id: str) -> dict[str, Any]:
        rec = self.db.get(HealthRecord, record_id)
        if rec is None:
            raise NotFoundError(f"健康记录不存在：{record_id}")
        return dump_record(rec)

    def create(self, body: HealthRecordCreate) -> dict[str, Any]:
        if body.kind not in KINDS:
            raise ValidationError(f"kind 非法：{body.kind}")
        if body.severity is not None and not (1 <= body.severity <= 5):
            raise ValidationError("severity 须在 1–5")
        rec = HealthRecord(
            kind=body.kind,
            title=body.title.strip(),
            occurred_at=to_utc(body.occurred_at),
            severity=body.severity,
            note=body.note,
            followup_needed=body.followup_needed,
            followup_due=body.followup_due,
        )
        self.db.add(rec)
        self.db.commit()
        self.db.refresh(rec)
        event_bus.publish(
            "health.record.created",
            payload={"id": str(rec.id), "kind": rec.kind, "title": rec.title},
            source="health",
        )
        if rec.followup_needed:
            publish_care_requested(rec)
        return dump_record(rec)

    def update(self, record_id: str, body: HealthRecordUpdate) -> dict[str, Any]:
        rec = self.db.get(HealthRecord, record_id)
        if rec is None:
            raise NotFoundError(f"健康记录不存在：{record_id}")
        data = body.model_dump(exclude_unset=True)
        if "kind" in data and data["kind"] is not None and data["kind"] not in KINDS:
            raise ValidationError(f"kind 非法：{data['kind']}")
        if "occurred_at" in data and data["occurred_at"] is not None:
            data["occurred_at"] = to_utc(data["occurred_at"])
        if data.get("severity") is not None and not (1 <= data["severity"] <= 5):
            raise ValidationError("severity 须在 1–5")
        for k, v in data.items():
            setattr(rec, k, v)
        self.db.add(rec)
        self.db.commit()
        self.db.refresh(rec)
        event_bus.publish(
            "health.record.updated",
            payload={"id": str(rec.id), "title": rec.title},
            source="health",
        )
        if rec.followup_needed:
            publish_care_requested(rec)
        return dump_record(rec)

    def delete(self, record_id: str) -> None:
        rec = self.db.get(HealthRecord, record_id)
        if rec is None:
            raise NotFoundError(f"健康记录不存在：{record_id}")
        self.db.delete(rec)
        self.db.commit()
        event_bus.publish(
            "health.record.deleted",
            payload={"id": record_id},
            source="health",
        )

    def request_followup(self, record_id: str) -> dict[str, Any]:
        rec = self.db.get(HealthRecord, record_id)
        if rec is None:
            raise NotFoundError(f"健康记录不存在：{record_id}")
        key = publish_care_requested(rec)
        return {
            "ok": True,
            "event_topic": EVENT_CARE,
            "idempotency_key": key,
            "record_id": str(rec.id),
        }
