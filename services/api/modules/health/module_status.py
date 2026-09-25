"""TX-O1-01 · 坞模块健康四态（结构态判定，只读只报目击）。

★ 四态：healthy / degraded / disabled / unknown。判定数据全部来自进程内状态
  （注册表 app.state.modules、激活表 registry.mounted()、激活目击
  activator.activated()/last_error()），零网络自探测——进程内自 HTTP 有
  自转发死锁前科（T18），高频轮询缓行（灵感 #005）；探测层（manifest
  healthcheck 透传）归 DRAFT-02 转正后的正式卡，本卡不出 last_ok_at
  （无探测来源，宁缺毋造）。
★ 与 E3 reconcile 并表：响应附 desired_count / scheduler_enabled，一眼同览。
★ census 零漂移：不动内核 /api/v1/modules（core/app.py 是内核领地），
  本端点长在 health 前缀下，纯附加字段。
★ 只报目击，不自动重启/禁用（TX-ACT-01 卡档缓行纪律同款）。
"""
from __future__ import annotations

from typing import Any

from sqlmodel import Session

from core.manifest import dependency_status

from .reconcile import list_desired_followups
from .reconcile_scheduler import scheduler_status
from .service import EVENT_CARE

STATUSES: tuple[str, ...] = ("healthy", "degraded", "disabled", "unknown")


def classify_module_status(
    *, registered: bool, activated: bool, activation_error: str | None
) -> str:
    """结构四态判定（纯函数，便于单测穷举）。

    优先级：未注册(unknown) > 激活报错(degraded) > 未激活(disabled) > 其余(healthy)。
    """
    if not registered:
        return "unknown"
    if activation_error is not None:
        return "degraded"
    if activated:
        return "healthy"
    return "disabled"


def _module_entry(
    mid: str,
    manifest: Any,
    *,
    activated: bool,
    error: str | None,
    available: set[str] | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = manifest if isinstance(manifest, dict) else {}
    api = data.get("api") or {}
    entry: dict[str, Any] = {
        "id": mid,
        "name": data.get("name"),
        "kind": data.get("kind"),
        "status": classify_module_status(
            registered=True, activated=activated, activation_error=error
        ),
        "activated": activated,
        "api_health_declared": bool(api.get("health")),
        "detail": error,
    }
    opts = [str(x) for x in (data.get("optionalDependencies") or [])]

    class _DepView:
        __slots__ = ("optionalDependencies",)

        def __init__(self, o: list[str]) -> None:
            self.optionalDependencies = o

    dep = dependency_status(_DepView(opts), available or set())
    entry["dep_state"] = dep.state
    entry["reason_code"] = dep.reason_code
    entry["missing"] = list(dep.missing)
    return entry


def dock_module_status(app: Any, db: Session) -> dict[str, Any]:
    """组装坞模块健康总览：四态清单 + 汇总计数 + reconcile 摘要。"""
    state = getattr(app, "state", None)
    registered: dict[str, dict[str, Any]] = getattr(state, "modules", None) or {}
    registry = getattr(state, "registry", None)
    mounted: list[str] = list(registry.mounted()) if registry is not None else []
    activator = getattr(state, "activator", None)
    # last_error 是 property（激活目击表），非方法——与 readyz 用法一致
    errors: dict[str, str] = dict(activator.last_error) if activator is not None else {}

    items: list[dict[str, Any]] = []
    summary = {s: 0 for s in STATUSES}
    available: set[str] = set()
    for manifest in registered.values():
        data = manifest if isinstance(manifest, dict) else {}
        for p in (data.get("provides") or []):
            available.add(str(p))
    for mid, manifest in registered.items():
        entry = _module_entry(
            mid, manifest, activated=mid in mounted, error=errors.get(mid), available=available
        )
        items.append(entry)
        summary[entry["status"]] += 1
    # 兜底目击：激活表里有、注册表里没有——如实报 unknown，不静默吞
    for mid in mounted:
        if mid not in registered:
            items.append(
                {
                    "id": mid,
                    "name": None,
                    "kind": None,
                    "status": "unknown",
                    "activated": True,
                    "api_health_declared": False,
                    "detail": "激活表存在但注册表缺失（异常目击）",
                }
            )
            summary["unknown"] += 1

    items.sort(key=lambda m: str(m["id"]))
    desired = list_desired_followups(db)
    return {
        "ok": True,
        "count": len(items),
        "modules": items,
        "summary": summary,
        "dep_degraded_count": sum(1 for m in items if m.get("dep_state") == "degraded"),
        "reconcile": {
            "event_topic": EVENT_CARE,
            "desired_count": len(desired),
            "scheduler_enabled": bool(scheduler_status().get("enabled")),
        },
    }
