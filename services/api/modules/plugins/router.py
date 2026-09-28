"""插件管理 API（T14 对外暴露的管理面）。

★ 不写 prefix=：内核按 manifest.api.base 自动挂 /api/v1/plugins。
★ 不自己捕获异常：内核统一转 RFC7807（manager 抛出的 AppError 自动变 problem+json）。
★ 每个端点都要 Request 注解（不能写 Any，否则会被当成必填查询参数 → 422）。

端点（对照总纲 §1.3 契约，路径前缀 /api/v1/plugins）：
  GET    /                     全部插件：id/名称/版本/类型/状态/扩展点/权限
  GET    /{id}                单个插件详情（含 manifest 原文、错误）
  POST   /{id}/enable         启用（幂等）
  POST   /{id}/disable        禁用（幂等；core 不可禁用）
  POST   /install             安装第三方插件（body: {"id": "..."}）
  POST   /{id}/uninstall      卸载（仅 third-party；必须清理干净）
  GET    /{id}/settings       读设置
  PATCH  /{id}/settings       写设置（按 settingsSchema 校验）
  GET    /{id}/health         单插件健康
  GET    /slots/{slotName}    某扩展点的全部贡献
  POST   /reload              重载（v0.1：返回需要重启才能生效的差异）
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, Request

from core.deps import get_current_user
from core.errors import ValidationError
from core.plugins import get_plugin_manager
from core.security import User

router = APIRouter()

MGR = get_plugin_manager()


def _registry(request: Request) -> Any:
    reg = getattr(request.app.state, "registry", None)
    if reg is None:
        raise RuntimeError("插件管理无法访问路由注册表（registry 未绑定）")
    return reg


@router.get("/health")
def health() -> dict[str, bool]:
    """插件子系统健康探针（恒 200）。"""
    return {"ok": True}


@router.get("")
def list_plugins(_user: User = Depends(get_current_user)) -> dict[str, Any]:  # noqa: B008
    plugins = MGR.list_plugins()
    """列出所有插件（含内核内置 / 第三方），带 `count`。"""
    return {"plugins": plugins, "count": len(plugins)}


@router.get("/{plugin_id}")
def get_plugin(plugin_id: str, _user: User = Depends(get_current_user)) -> dict[str, Any]:  # noqa: B008
    """读单个插件的完整清单与运行态（启用状态 / 权限 / 设置 schema）。"""
    return MGR.get_plugin(plugin_id)


@router.post("/{plugin_id}/enable")
def enable_plugin(
    plugin_id: str,
    request: Request,
    _user: User = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    return MGR.enable(plugin_id, _registry(request))


@router.post("/{plugin_id}/disable")
def disable_plugin(
    plugin_id: str,
    request: Request,
    _user: User = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    result = MGR.disable(plugin_id, _registry(request))
    # TX-ACT-01：禁用的插件同时清掉激活器的 pending 登记，
    # 防止事件命中把已禁用插件重新挂回路由（击穿 disable 语义）。
    activator = getattr(request.app.state, "activator", None)
    if activator is not None:
        activator.clear_pending(plugin_id)
    return result


@router.post("/install")
def install_plugin(
    request: Request,
    body: dict[str, Any] = Body(...),
    _user: User = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    plugin_id = body.get("id")
    if not plugin_id:
        raise ValidationError("install 需要 body: {\"id\": \"<插件id>\"}")
    """安装插件（`plugin_id` 取自上传包解析出的标识）。⚠️ 安装 ≠ 启用。"""
    return MGR.install(plugin_id, _registry(request))


@router.post("/{plugin_id}/uninstall")
def uninstall_plugin(
    plugin_id: str,
    request: Request,
    _user: User = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    """卸载插件（**先停用再卸载**；插件数据保留，不会被删）。"""
    return MGR.uninstall(plugin_id, _registry(request))


@router.get("/{plugin_id}/settings")
def get_settings(
    plugin_id: str, _user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """读某个插件的设置（结构按它的 `settings.schema.json`）。"""
    return {"plugin_id": plugin_id, "settings": MGR.get_settings(plugin_id)}


@router.patch("/{plugin_id}/settings")
def patch_settings(
    plugin_id: str,
    body: dict[str, Any] = Body(...),
    _user: User = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    return {"plugin_id": plugin_id, "settings": MGR.set_settings(plugin_id, body)}


@router.get("/{plugin_id}/health")
def plugin_health(
    plugin_id: str, _user: User = Depends(get_current_user)
) -> dict[str, Any]:
    return MGR.health(plugin_id)


@router.get("/slots/{slot_name}")
def slot_contributions(
    slot_name: str, _user: User = Depends(get_current_user)
) -> dict[str, Any]:
    return {"slot": slot_name, "contributions": MGR.slots(slot_name)}


@router.post("/reload")
def reload_plugins(
    request: Request, _user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """v0.1：扫描磁盘与运行时差异，返回需要重启才能生效的插件（v0.2 再做零重启）。"""
    reg = _registry(request)
    mounted = set(reg.mounted())
    diffs: list[dict[str, Any]] = []
    for item in MGR.list_plugins():
        pid = item.get("id")
        if not pid:
            continue
        enabled = item.get("enabled", True)
        is_mounted = pid in mounted
        if enabled != is_mounted:
            diffs.append(
                {"id": pid, "enabled": enabled, "mounted": is_mounted, "needs_restart": True}
            )
    return {"reload_required": diffs, "count": len(diffs)}
