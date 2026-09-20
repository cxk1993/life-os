"""E3 · 健康期望状态 reconcile（声明式跟进 + 周期/按需收敛）。

★ 期望态：所有 `followup_needed=true` 的健康记录，都应有对应跟进待办。
★ 收敛方式：health 侧重新 publish `health.care.requested`（幂等键不变）；
  消费方 todo（ISSUE-007 health_link）按 `source_path` 幂等创建/跳过。
★ ADR-0002：绝不 import todo、绝不读他插件表。
"""
from __future__ import annotations

import logging
from typing import Any

from sqlmodel import Session, col, select

from core.config import read_setting

from .models import HealthRecord
from .service import EVENT_CARE, dump_record, publish_care_requested

log = logging.getLogger("health.reconcile")


def _enabled() -> bool:
    return (read_setting("HEALTH_RECONCILE_ENABLED", "false") or "false").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def list_desired_followups(db: Session) -> list[HealthRecord]:
    stmt = (
        select(HealthRecord)
        .where(col(HealthRecord.followup_needed) == True)  # noqa: E712
        .order_by(col(HealthRecord.occurred_at).desc())
    )
    return list(db.exec(stmt).all())


def reconcile_followups(db: Session) -> dict[str, Any]:
    """广播期望态：对每条 followup_needed 记录重发 care.requested。

    返回摘要（只读业务结果，不改健康记录字段）。
    """
    records = list_desired_followups(db)
    published: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for rec in records:
        try:
            key = publish_care_requested(rec)
            published.append(
                {
                    "record_id": str(rec.id),
                    "title": rec.title,
                    "idempotency_key": key,
                    "followup_due": rec.followup_due.isoformat() if rec.followup_due else None,
                }
            )
        except Exception as exc:  # noqa: BLE001 — 单条失败不中断整轮
            log.warning("reconcile publish 失败 record=%s: %s", rec.id, exc)
            errors.append({"record_id": str(rec.id), "error": str(exc)})
    summary = {
        "ok": not errors,
        "event_topic": EVENT_CARE,
        "desired_count": len(records),
        "published_count": len(published),
        "error_count": len(errors),
        "published": published,
        "errors": errors,
        "mode": "desired-state-broadcast",
        "scheduler_enabled": _enabled(),
    }
    log.info(
        "health reconcile: desired=%s published=%s errors=%s",
        summary["desired_count"],
        summary["published_count"],
        summary["error_count"],
    )
    return summary


def reconcile_status(db: Session) -> dict[str, Any]:
    """只读：期望态规模 + 调度开关（不 publish）。"""
    records = list_desired_followups(db)
    return {
        "event_topic": EVENT_CARE,
        "desired_count": len(records),
        "scheduler_enabled": _enabled(),
        "records": [dump_record(r) for r in records],
    }
