"""事件联动：calendar.reminder.fired → Web Push 广播（浏览器侧推送通道）。

★ ISSUE-007/health_link 同款模式：包装 event_bus.publish，不改 core/events.py；
  不 import calendar 插件本体，只消费事件 payload（ADR-0002 硬规则）。
★ 桌面通知走桥（T25 已投递 Windows toast），本联动补的是「浏览器/PWA 窗口」通道，
  两者并行——手机 Chrome、主人没开桌面时也能收到。
"""
from __future__ import annotations

import logging
from contextlib import suppress
from typing import Any

from core.deps import get_db
from core.events import event_bus

from .sender import send_broadcast

log = logging.getLogger("push.link")

EVENT_REMINDER = "calendar.reminder.fired"
_installed = False


def handle_reminder_event(event: dict[str, Any]) -> None:
    if not isinstance(event, dict) or event.get("topic") != EVENT_REMINDER:
        return
    payload = event.get("payload")
    if not isinstance(payload, dict):
        return
    title = f"日程提醒：{payload.get('title') or ''}".strip()
    start_s = str(payload.get("start_at") or "")
    db = get_db()
    try:
        out = send_broadcast(
            db, title=title, body=f"开始：{start_s}" if start_s else "",
            url="/", tag=f"reminder-{payload.get('event_id') or ''}", topic=EVENT_REMINDER,
        )
        log.info(
            "reminder → web push",
            extra={"sent": out.get("sent"), "pruned": out.get("pruned")},
        )
    except Exception as exc:  # noqa: BLE001 — 联动失败不打断事件广播
        log.warning("reminder push 联动失败: %s", exc)
    finally:
        with suppress(Exception):
            db.close()


def install_push_link() -> bool:
    """注册事件监听（幂等）。"""
    global _installed
    if _installed:
        return False
    event_bus.add_listener(handle_reminder_event)
    _installed = True
    log.info("push 事件联动已装载（%s → web push）", EVENT_REMINDER)
    return True


# router.py 被内核挂载时即装载（health_link 由 todo/router import 触发，同款时序）。
install_push_link()
