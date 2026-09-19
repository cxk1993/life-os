"""T25 日程到期提醒：扫描 calendar_event → 本机桥桌面通知。

★ ADR-0002：不 import 其他插件（含 notes）。签名算法与 services/bridge/protocol.py
  **逐字节一致**；ISSUE-005 若落地「通用适配器」，本文件的 _sign 可平滑替换。
★ 默认关闭：CALENDAR_REMINDER_ENABLED=true 才在进程内启动。
★ v0.1 去重：进程内内存表（重启后可能重复弹一次）；持久化去重待正式卡增强。
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlmodel import Session, col, select

from core.config import get_settings, read_setting
from core.events import event_bus
from modules.calendar.models import CalendarEvent, CalendarReminderLog

log = logging.getLogger("calendar.reminder")

_lock_state: dict[str, Any] = {"scheduler": None, "notified": {}}


def _canonical(method: str, path: str, ts: int, nonce: str, body: bytes) -> str:
    return f"{method.upper()}|{path}|{ts}|{nonce}|{body.decode('utf-8', 'replace')}"


def _sign(psk: str, method: str, path: str, ts: int, nonce: str, body: bytes = b"") -> str:
    msg = _canonical(method, path, ts, nonce, body).encode("utf-8")
    return hmac.new(psk.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def _enabled() -> bool:
    raw = (read_setting("CALENDAR_REMINDER_ENABLED", "false") or "false").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _lead_minutes() -> int:
    raw = read_setting("CALENDAR_REMINDER_LEAD_MINUTES", "0") or "0"
    try:
        return max(0, int(raw))
    except ValueError:
        return 0


def _poll_seconds() -> int:
    raw = read_setting("CALENDAR_REMINDER_POLL_SECONDS", "30") or "30"
    try:
        return max(10, int(raw))
    except ValueError:
        return 30


def bridge_notify(title: str, body: str, *, channel: str = "auto", timeout: float = 5.0) -> dict:
    """云侧 → 本机桥 /bridge/notify（签名含 JSON body）。"""
    settings = get_settings()
    base = (getattr(settings, "bridge_url", "") or "").rstrip("/")
    psk = getattr(settings, "bridge_psk", "") or ""
    if not base or not psk:
        raise RuntimeError("未配置 BRIDGE_URL / BRIDGE_PSK")
    payload = {"title": title, "body": body, "app_id": "Life-OS", "channel": channel}
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    path = "/bridge/notify"
    ts = int(time.time())
    nonce = uuid.uuid4().hex
    headers = {
        "X-Bridge-PSK": psk,
        "X-Bridge-Ts": str(ts),
        "X-Bridge-Nonce": nonce,
        "X-Bridge-Sign": _sign(psk, "POST", path, ts, nonce, raw),
        "Content-Type": "application/json; charset=utf-8",
    }
    resp = httpx.post(base + path, headers=headers, content=raw, timeout=timeout)
    if resp.status_code >= 400:
        raise RuntimeError(f"桥返回 {resp.status_code}: {resp.text[:200]}")
    data = resp.json()
    return data if isinstance(data, dict) else {"ok": False}


def _already_fired_ids(db: Session, event_ids: list[str]) -> set[str]:
    """持久化去重：calendar_reminder_log 中已成功投递的 event_id。"""
    if not event_ids:
        return set()
    rows = db.exec(
        select(col(CalendarReminderLog.event_id)).where(
            col(CalendarReminderLog.event_id).in_(event_ids),
            col(CalendarReminderLog.ok) == True,  # noqa: E712
        )
    ).all()
    return {str(r) for r in rows}


def collect_due_events(
    db: Session,
    *,
    now: datetime | None = None,
    lead_minutes: int = 0,
    grace_minutes: int = 2,
) -> list[CalendarEvent]:
    """收集 [now-grace, now+lead] 内开始的事件（跳过已通知、跳过 all_day）。"""
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    start = now - timedelta(minutes=grace_minutes)
    end = now + timedelta(minutes=max(0, lead_minutes))
    rows = db.exec(
        select(CalendarEvent).where(
            col(CalendarEvent.start_at) >= start,
            col(CalendarEvent.start_at) <= end,
            col(CalendarEvent.all_day) == False,  # noqa: E712
        )
    ).all()
    notified: dict[str, float] = _lock_state["notified"]
    fired_db = _already_fired_ids(db, [str(e.id) for e in rows])
    due: list[CalendarEvent] = []
    for ev in rows:
        key = str(ev.id)
        if key in notified or key in fired_db:
            continue
        due.append(ev)
    return due


def mark_notified(event_id: str, *, now: float | None = None) -> None:
    notified: dict[str, float] = _lock_state["notified"]
    notified[str(event_id)] = now if now is not None else time.time()
    if len(notified) > 2000:
        cutoff = time.time() - 86400
        for k in [k for k, t in notified.items() if t < cutoff]:
            notified.pop(k, None)


def _write_log(
    db: Session,
    *,
    event_id: str,
    title: str,
    channel: str,
    ok: bool,
    detail: str | None,
    fired_at: datetime | None = None,
) -> None:
    row = CalendarReminderLog(
        event_id=str(event_id),
        fired_at=fired_at or datetime.now(UTC),
        title=title[:200],
        channel=channel[:20],
        ok=ok,
        detail=(detail or None) and detail[:500],
    )
    db.add(row)
    db.commit()


def list_reminder_logs(db: Session, limit: int = 50) -> list[dict[str, Any]]:
    from sqlalchemy import desc
    from sqlmodel import col

    rows = db.exec(
        select(CalendarReminderLog)
        .order_by(desc(col(CalendarReminderLog.fired_at)))
        .limit(max(1, min(limit, 200)))
    ).all()
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "id": str(r.id),
                "event_id": r.event_id,
                "title": r.title,
                "fired_at": r.fired_at.isoformat() if r.fired_at else None,
                "channel": r.channel,
                "ok": r.ok,
                "detail": r.detail,
            }
        )
    return out


def run_reminder_tick(
    db: Session,
    *,
    notify_fn: Any | None = None,
    now: datetime | None = None,
    lead_minutes: int | None = None,
    channel: str = "auto",
) -> list[dict[str, Any]]:
    """一轮扫描 + 投递。notify_fn(title, body) 可注入（测试用）。"""
    lead = _lead_minutes() if lead_minutes is None else lead_minutes
    send = notify_fn or (lambda t, b: bridge_notify(t, b, channel=channel))
    due = collect_due_events(db, now=now, lead_minutes=lead)
    results: list[dict[str, Any]] = []
    for ev in due:
        title = f"日程提醒：{ev.title}"
        start_s = ev.start_at.isoformat() if ev.start_at else ""
        body = f"{ev.title}\n开始：{start_s}" + (f"\n{ev.note}" if ev.note else "")
        row: dict[str, Any] = {"event_id": str(ev.id), "title": ev.title}
        ok = False
        detail: str | None = None
        try:
            out = send(title, body)
            ok = bool(isinstance(out, dict) and out.get("ok", True))
            row["ok"] = ok
            row["bridge"] = out if isinstance(out, dict) else None
            detail = str((out or {}).get("detail") or (out or {}).get("channel") or "")[:200]
            if ok:
                mark_notified(str(ev.id))
                try:
                    event_bus.publish(
                        "calendar.reminder.fired",
                        payload={
                            "event_id": str(ev.id),
                            "title": ev.title,
                            "start_at": start_s,
                            "channel": channel,
                        },
                        source="calendar",
                    )
                except Exception as bus_exc:  # noqa: BLE001
                    log.warning("publish calendar.reminder.fired failed: %s", bus_exc)
        except Exception as exc:  # noqa: BLE001
            row["ok"] = False
            row["error"] = str(exc)[:200]
            detail = row["error"]
            ok = False
        try:
            _write_log(
                db,
                event_id=str(ev.id),
                title=ev.title,
                channel=channel,
                ok=ok,
                detail=detail,
            )
        except Exception as log_exc:  # noqa: BLE001
            log.warning("write reminder log failed: %s", log_exc)
        results.append(row)
    if results:
        log.info("calendar reminder tick", extra={"count": len(results)})
    return results


def start_scheduler() -> bool:
    """Interval 调度：默认关。与 finance 同模式。"""
    if not _enabled():
        log.info("calendar 提醒未启用（CALENDAR_REMINDER_ENABLED!=true）")
        return False
    if _lock_state.get("scheduler") is not None:
        return False
    from contextlib import suppress

    from apscheduler.schedulers.background import (
        BackgroundScheduler,  # type: ignore[import-untyped]
    )

    def _job() -> None:
        from core.deps import get_db

        db = get_db()
        try:
            run_reminder_tick(db)
        except Exception as exc:  # noqa: BLE001
            log.warning("calendar reminder tick failed: %s", exc)
        finally:
            with suppress(Exception):
                db.close()

    sched = BackgroundScheduler(timezone="Asia/Shanghai")
    sched.add_job(
        _job,
        "interval",
        seconds=_poll_seconds(),
        id="calendar_reminder",
        max_instances=1,
        coalesce=True,
    )
    sched.start()
    _lock_state["scheduler"] = sched
    log.info(
        "calendar 提醒调度已启动",
        extra={"poll_s": _poll_seconds(), "lead_m": _lead_minutes()},
    )
    return True


def stop_scheduler() -> None:
    from contextlib import suppress

    sched = _lock_state.get("scheduler")
    if sched is None:
        return
    with suppress(Exception):
        sched.shutdown(wait=False)
    _lock_state["scheduler"] = None


def scheduler_status() -> dict[str, Any]:
    return {
        "enabled": _enabled(),
        "running": _lock_state.get("scheduler") is not None,
        "lead_minutes": _lead_minutes(),
        "poll_seconds": _poll_seconds(),
        "notified_count": len(_lock_state.get("notified") or {}),
        "log_table": "calendar_reminder_log",
    }
