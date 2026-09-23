"""Web Push 发送核心（push 插件领地；ADR-0003：AI/前端经 REST，不 import 其他插件）。

设计：
- VAPID 密钥从环境变量 / 项目根 .env 读（read_setting 先例，Settings 未声明字段吞值的坑）。
  PUSH_VAPID_PUBLIC_KEY / PUSH_VAPID_PRIVATE_KEY / PUSH_VAPID_CLAIMS_EMAIL
- pywebpush 惰性 import：没装依赖时插件可加载、health 报 pywebpush_installed=False，
  发送明确报错——不许静默假成功（铁律 #8）。
- 订阅 endpoint 唯一：重复订阅刷新 keys + 复活 active（浏览器换 key 场景）。
- 404/410 响应 = 订阅失效：标 inactive（prune），不再重试轰炸。
- 每次批量发送落 push_log（审计：谁被推了什么）。
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session, col, select

from core.config import read_setting
from core.errors import ValidationError

from .models import PushLog, PushSubscription

log = logging.getLogger("push")

# 失效订阅的 HTTP 状态（RFC 8030/8292 惯例：404/410 = gone）
_GONE_STATUS = {404, 410}


def vapid_keys() -> tuple[str, str, str]:
    pub = (read_setting("PUSH_VAPID_PUBLIC_KEY", "") or "").strip()
    priv = (read_setting("PUSH_VAPID_PRIVATE_KEY", "") or "").strip()
    claims = (read_setting("PUSH_VAPID_CLAIMS_EMAIL", "mailto:admin@localhost") or "").strip()
    return pub, priv, claims


def vapid_ready() -> bool:
    pub, priv, _ = vapid_keys()
    return bool(pub and priv)


def pywebpush_available() -> bool:
    try:
        import pywebpush  # type: ignore[import-untyped]  # noqa: F401
        return True
    except ImportError:
        return False


def subscribe(
    db: Session, data: dict[str, Any], *, user_agent: str | None = None
) -> PushSubscription:
    """登记/刷新订阅。endpoint 已存在 → 更新 keys、复活。"""
    endpoint = str(data.get("endpoint") or "").strip()
    keys = data.get("keys") or {}
    p256dh = str(keys.get("p256dh") or "").strip()
    auth = str(keys.get("auth") or "").strip()
    if not endpoint or not p256dh or not auth:
        raise ValidationError("订阅缺 endpoint/keys.p256dh/keys.auth")
    stmt = select(PushSubscription).where(col(PushSubscription.endpoint) == endpoint)
    row = db.exec(stmt).first()
    ua_raw = user_agent or data.get("user_agent")
    ua = (str(ua_raw)[:200] if ua_raw else None)
    if row is None:
        row = PushSubscription(
            endpoint=endpoint, p256dh=p256dh, auth=auth, user_agent=ua,
        )
        db.add(row)
    else:
        row.p256dh, row.auth = p256dh, auth
        if ua:
            row.user_agent = ua
        row.active = True
        row.fail_count = 0
    db.commit()
    db.refresh(row)
    return row


def unsubscribe(db: Session, endpoint: str) -> bool:
    stmt = select(PushSubscription).where(col(PushSubscription.endpoint) == endpoint.strip())
    row = db.exec(stmt).first()
    if row is None:
        return False
    row.active = False
    db.add(row)
    db.commit()
    return True


def list_active(db: Session) -> list[PushSubscription]:
    return list(db.exec(select(PushSubscription).where(col(PushSubscription.active) == True)).all())  # noqa: E712


def _send_one(
    sub: PushSubscription, title: str, body: str, url: str, tag: str
) -> tuple[bool, int | None, str]:
    from pywebpush import WebPushException, webpush  # 惰性：依赖缺失时调用方兜错

    pub, priv, claims = vapid_keys()
    payload = {"title": title, "body": body, "url": url, "tag": tag}
    try:
        resp = webpush(
            subscription_info={
                "endpoint": sub.endpoint,
                "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
            },
            data=json_dumps(payload),
            vapid_private_key=priv,
            vapid_claims={"sub": claims},
            ttl=3600,
        )
        status = getattr(resp, "status_code", 201)
        return (200 <= status < 300), status, ""
    except WebPushException as exc:
        status = None
        resp = getattr(exc, "response", None)
        if resp is not None:
            status = getattr(resp, "status_code", None)
        return False, status, str(exc)[:200]
    except Exception as exc:  # noqa: BLE001 — 单订阅失败不拖垮批次
        return False, None, str(exc)[:200]


def json_dumps(obj: Any) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False)


def send_broadcast(
    db: Session,
    *,
    title: str,
    body: str = "",
    url: str = "/",
    tag: str = "lifeos",
    topic: str = "manual",
) -> dict[str, Any]:
    """向全部活跃订阅广播。返回 {ok, sent, pruned, detail}。写 push_log。"""
    subs = list_active(db)
    if not vapid_ready() or not pywebpush_available():
        missing = []
        if not vapid_ready():
            missing.append("VAPID 密钥（PUSH_VAPID_PUBLIC_KEY/PRIVATE_KEY）")
        if not pywebpush_available():
            missing.append("pywebpush 库")
        detail = "推送未配置：" + "、".join(missing)
        db.add(
            PushLog(
                topic=topic,
                title=title[:200],
                body=body[:2000] or None,
                ok=False,
                detail=detail,
                sent_at=datetime.now(UTC),
            )
        )
        db.commit()
        return {"ok": False, "sent": 0, "pruned": 0, "detail": detail}

    sent = 0
    pruned = 0
    errs: list[str] = []
    now = datetime.now(UTC)
    for sub in subs:
        ok, status, err = _send_one(sub, title, body, url, tag)
        sub.last_sent_at = now
        sub.last_status = status
        if ok:
            sent += 1
            sub.fail_count = 0
        else:
            sub.fail_count += 1
            if status in _GONE_STATUS:
                sub.active = False
                pruned += 1
            errs.append(err or f"status={status}")
        db.add(sub)
    db.add(PushLog(
        topic=topic, title=title[:200], body=body[:2000] or None,
        ok=sent > 0 or not subs, detail=("; ".join(errs)[:500] or None), sent_at=now,
    ))
    db.commit()
    if sent or not subs:
        log.info("push broadcast", extra={"topic": topic, "sent": sent, "pruned": pruned})
    return {"ok": sent > 0 or not subs, "sent": sent, "pruned": pruned,
            "detail": ("; ".join(errs)[:500] or None)}
