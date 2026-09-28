"""push 插件路由（Web Push 订阅管理 + 手动广播 + 审计流水）。

HTTP 契约（全项目统一）：
  成功 → 资源 JSON；失败 → 内核统一 RFC7807 problem+json。
★ 不加 `from __future__ import annotations`（内核纪律，见 calendar/router.py 头注）。
★ 前缀由内核按 manifest.api.base 自动加（/api/v1/push）。

端点总览：
  GET    /health             存活 + 配置态（VAPID/依赖/活跃订阅数）
  GET    /vapid-public-key   VAPID 公钥（前端注册 serviceWorker 用；公钥可公开）
  POST   /subscribe          登记订阅（不鉴权：endpoint URL 本身即设备能力凭证，Web Push 惯例）
  DELETE /subscribe          注销订阅（同上）
  GET    /subscriptions      订阅列表（登录）
  POST   /send               手动广播（登录；验收/排障）
  GET    /logs               投递流水（登录）
"""
import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlmodel import Session, col, select

from core.deps import get_current_user, get_db
from core.errors import ValidationError

from . import push_link as _push_link  # noqa: F401,E402  事件联动装载（health_link 先例）
from .models import PushLog, PushSubscription
from .schema import (
    PushHealthOut,
    SendIn,
    SendResultOut,
    SubscribeIn,
    SubscriptionOut,
)
from .sender import (
    list_active,
    pywebpush_available,
    send_broadcast,
    subscribe,
    unsubscribe,
    vapid_keys,
    vapid_ready,
)

router = APIRouter()

_MANIFEST_PATH = Path(__file__).resolve().parent / "manifest.json"
with _MANIFEST_PATH.open(encoding="utf-8") as _f:
    _MANIFEST = json.load(_f)

DbDep = Session


@router.get("/health", response_model=PushHealthOut)
def health(db: Annotated[DbDep, Depends(get_db)]) -> PushHealthOut:
    """推送通道自检：VAPID 密钥是否就绪、pywebpush 是否装上、当前有几台活跃订阅。

    `vapid_ready=false` 或 `pywebpush_installed=false` 时，`/send` 必然失败 —— 先看这里。
    """
    return PushHealthOut(
        enabled=True,
        vapid_ready=vapid_ready(),
        pywebpush_installed=pywebpush_available(),
        subscriptions_active=len(list_active(db)),
    )


@router.get("/manifest")
def manifest() -> dict:
    """本插件的清单（能力面/事件面）。"""
    return _MANIFEST


@router.get("/vapid-public-key")
def vapid_public_key() -> dict:
    """VAPID 公钥（前端注册 serviceWorker 用；**公钥可公开**）。"""
    pub, _, _ = vapid_keys()
    if not pub:
        raise ValidationError("服务端未配置 PUSH_VAPID_PUBLIC_KEY，浏览器推送暂不可用")
    return {"public_key": pub}


@router.post("/subscribe", response_model=SubscriptionOut)
def api_subscribe(
    body: SubscribeIn,
    request: Request,
    db: Annotated[DbDep, Depends(get_db)],
) -> SubscriptionOut:
    """登记一个浏览器推送订阅（**不鉴权** —— Web Push 惯例：endpoint 本身就是设备能力凭证）。

    前端 `pushManager.subscribe()` 拿到订阅后 POST 到这里；重复登记同一 endpoint 会刷新密钥并复活。
    """
    ua = request.headers.get("user-agent")
    row = subscribe(db, body.model_dump(), user_agent=ua)
    return _sub_out(row)


@router.delete("/subscribe")
def api_unsubscribe(
    endpoint: Annotated[
        str,
        Query(
            min_length=20, max_length=500,
            description="要注销的订阅地址（就是当初 POST /subscribe 时传的那个 endpoint）",
        ),
    ],
    db: Annotated[DbDep, Depends(get_db)],
) -> dict:
    """注销一个订阅（同样不鉴权）。"""
    return {"ok": unsubscribe(db, endpoint)}


@router.get("/subscriptions", response_model=list[SubscriptionOut])
def api_subscriptions(
    db: Annotated[DbDep, Depends(get_db)],
    _user: Annotated[dict, Depends(get_current_user)],
) -> list[SubscriptionOut]:
    """列出全部订阅（含 active 状态、上次投递状态码、失败次数）。"""
    rows = db.exec(select(PushSubscription).order_by(col(PushSubscription.created_at))).all()
    return [_sub_out(r) for r in rows]


@router.post("/send", response_model=SendResultOut)
def api_send(
    body: SendIn,
    db: Annotated[DbDep, Depends(get_db)],
    _user: Annotated[dict, Depends(get_current_user)],
) -> SendResultOut:
    """**手动广播**一条推送给所有活跃订阅（验收 / 排障 / AI 主动推送都走这条）。

    返回 `{ok, sent, pruned, detail}`：`sent` = 实际送达台数，`pruned` = 因 404/410 被判失效而清理的订阅数。
    """
    out = send_broadcast(
        db, title=body.title, body=body.body, url=body.url, tag=body.tag, topic="manual"
    )
    return SendResultOut(**out)


@router.get("/logs")
def api_logs(
    db: Annotated[DbDep, Depends(get_db)],
    _user: Annotated[dict, Depends(get_current_user)],
    limit: int = Query(default=50, ge=1, le=200, description="返回条数上限（1–200，默认 50）"),
) -> list[dict]:
    """投递流水（最近 N 条，含 topic / 标题 / 是否成功 / 失败详情）。
    想知道"某条推送到底发出去没有"，看这里。
    """
    rows = db.exec(
        select(PushLog).order_by(col(PushLog.sent_at).desc()).limit(max(1, min(limit, 200)))
    ).all()
    return [
        {
            "id": str(r.id), "topic": r.topic, "title": r.title, "body": r.body,
            "ok": r.ok, "detail": r.detail,
            "sent_at": r.sent_at.isoformat() if r.sent_at else None,
        }
        for r in rows
    ]


def _sub_out(row: PushSubscription) -> SubscriptionOut:
    return SubscriptionOut(
        id=str(row.id),
        endpoint_prefix=row.endpoint[:40],
        user_agent=row.user_agent,
        active=row.active,
        last_sent_at=row.last_sent_at,
        last_status=row.last_status,
        fail_count=row.fail_count,
        created_at=row.created_at,
    )
