"""插件管理器（总纲 §1.3 / 验收 B）：install / enable / disable / uninstall / 设置。

★ 注册表(plugin_state)与运行时对象(挂载的 router)分离 —— 这是热插拔的前提，
  也是"一切皆插件"不被腐蚀的结构保障。

职责边界（不抢别人的活）：
  - 发现/校验/版本/权限/迁移/设置/生命周期 分别由同包其它模块负责，这里只编排。
  - 路由挂载/摘掉 交给 core.registry.ModuleRegistry（T03 的 RouterHost）。
  - 数据库表/会话 交给 db（T04）。
"""
from __future__ import annotations

import json
import logging
import shutil
from typing import Any

from sqlmodel import select

from core.deps import get_db
from core.errors import ConflictError, ForbiddenError, NotFoundError
from core.plugins import discover as discover_mod
from core.plugins.discover import DiscoveryResult, PluginInfo, mount_plugin
from core.plugins.lifecycle import run_lifecycle_hook
from core.plugins.migrations import rollback_migrations, run_migrations
from core.plugins.permissions import is_valid_permission
from core.plugins.settings import read_settings, write_settings
from db.models.system import PluginSetting, PluginState

log = logging.getLogger("kernel.plugins")

_BUILTIN_INCLUSION_NOTE = "内置插件随系统发布，不需要 install；可直接 enable/disable。"


class PluginManager:
    """单例式编排器。每调用即时重新发现（发现很便宜，且保证看到磁盘最新状态）。"""

    # ───────────────────────── 发现 ─────────────────────────
    def discover(self) -> DiscoveryResult:
        return discover_mod.discover_plugins()

    def _require(self, plugin_id: str) -> PluginInfo:
        for p in self.discover().plugins:
            if p.id == plugin_id:
                return p
        raise NotFoundError(f"插件不存在或校验未通过：{plugin_id!r}")

    def list_plugins(self) -> list[dict[str, Any]]:
        result = self.discover()
        with get_db() as db:
            states = {
                s.id: s
                for s in db.exec(select(PluginState)).all()
            }
        out: list[dict[str, Any]] = []
        for p in result.plugins:
            st = states.get(p.id)
            enabled = st.enabled if st is not None else True
            granted = (
                json.loads(st.granted_permissions)
                if st and st.granted_permissions
                else list(p.manifest.get("permissions", []))
            )
            out.append(
                {
                    "id": p.id,
                    "name": p.manifest.get("name"),
                    "version": p.manifest.get("version"),
                    "kind": p.kind,
                    "source": p.source,
                    "enabled": enabled,
                    "permissions": granted,
                    "slots": p.manifest.get("slots", []),
                    "provides": p.manifest.get("provides", []),
                    "requires": p.manifest.get("requires", []),
                    "last_error": st.last_error if st else None,
                    "valid": True,
                }
            )
        # 也列出校验失败但目录存在的插件（让用户知道为什么没起来）
        for err in result.errors:
            out.append(
                {
                    "directory": str(err.directory),
                    "source": err.source,
                    "valid": False,
                    "error": err.message,
                }
            )
        return out

    def get_plugin(self, plugin_id: str) -> dict[str, Any]:
        for item in self.list_plugins():
            if item.get("id") == plugin_id:
                return item
        raise NotFoundError(f"插件不存在：{plugin_id!r}")

    def slots(self, slot_name: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for p in self.discover().plugins:
            if slot_name in p.manifest.get("slots", []):
                out.append(
                    {
                        "plugin_id": p.id,
                        "name": p.manifest.get("name"),
                        "enabled": self._enabled(p.id),
                    }
                )
        return out

    def _enabled(self, plugin_id: str) -> bool:
        with get_db() as db:
            st = db.get(PluginState, plugin_id)
        return st.enabled if st else True

    # ───────────────────────── 状态落库 ─────────────────────────
    def _upsert_state(
        self,
        info: PluginInfo,
        *,
        enabled: bool,
        last_error: str | None = None,
    ) -> None:
        manifest = info.manifest
        granted = list(manifest.get("permissions", []))
        with get_db() as db:
            st = db.get(PluginState, info.id)
            if st is None:
                st = PluginState(id=info.id)
                db.add(st)
            st.version = manifest.get("version", "0.0.0")
            st.kind = info.kind
            st.enabled = enabled
            st.last_error = last_error
            st.granted_permissions = json.dumps(granted, ensure_ascii=False)
            db.commit()

    # ───────────────────────── 挂载 / 摘卸载 ─────────────────────────
    # 挂载统一走 core.plugins.discover.mount_plugin（TX-ACT-01 前置小步：
    # 与 create_app 启动全量挂载共用单一入口，本类不再各写一份）。
    def _unmount(self, info: PluginInfo, registry: Any) -> None:
        if info.id in registry.mounted():
            registry.unmount(info.id)

    # ───────────────────────── 启停 ─────────────────────────
    def enable(self, plugin_id: str, registry: Any) -> dict[str, Any]:
        info = self._require(plugin_id)
        if info.kind == "core":
            # core 永远启用；这里只确保状态正确，不摘挂。
            self._upsert_state(info, enabled=True)
            return self.get_plugin(plugin_id)
        self._upsert_state(info, enabled=True, last_error=None)
        try:
            mount_plugin(info, registry)
            err = run_lifecycle_hook(info, "enable", db=get_db())
        except Exception as exc:  # noqa: BLE001
            self._upsert_state(info, enabled=True, last_error=str(exc))
            raise
        if err:
            self._upsert_state(info, enabled=True, last_error=err)
        return self.get_plugin(plugin_id)

    def disable(self, plugin_id: str, registry: Any) -> dict[str, Any]:
        info = self._require(plugin_id)
        if info.kind == "core":
            raise ForbiddenError(f"内核插件「{plugin_id}」不可禁用（kind=core）")
        self._unmount(info, registry)
        err = run_lifecycle_hook(info, "disable", db=get_db())
        self._upsert_state(info, enabled=False, last_error=err)
        return self.get_plugin(plugin_id)

    # ───────────────────────── 安装 / 卸载（仅 third-party） ─────────────────────────
    def install(self, plugin_id: str, registry: Any) -> dict[str, Any]:
        info = self._require(plugin_id)
        if info.kind in ("core", "builtin"):
            raise ConflictError(
                f"插件「{plugin_id}」是 {info.kind}，{_BUILTIN_INCLUSION_NOTE}"
            )
        # 校验权限声明合法
        for perm in info.manifest.get("permissions", []):
            if not is_valid_permission(perm):
                raise ForbiddenError(f"插件「{plugin_id}」声明了非法权限：{perm!r}")
        # 建表
        from db.engine import get_engine

        engine = get_engine()
        run_migrations(engine, info)
        run_lifecycle_hook(info, "install", db=get_db())
        self._upsert_state(info, enabled=True, last_error=None)
        mount_plugin(info, registry)
        return self.get_plugin(plugin_id)

    def uninstall(self, plugin_id: str, registry: Any) -> dict[str, Any]:
        info = self._require(plugin_id)
        if info.kind in ("core", "builtin"):
            raise ForbiddenError(
                f"插件「{plugin_id}」是 {info.kind}，不可卸载"
                "（builtin/core 随系统发布，只能禁用）。"
            )
        # 1) 生命周期 on_uninstall
        run_lifecycle_hook(info, "uninstall", db=get_db())
        # 2) 摘掉路由（扩展点注册清理）
        self._unmount(info, registry)
        # 3) 回滚迁移（删表）
        from db.engine import get_engine

        engine = get_engine()
        rollback_migrations(engine, info)
        # 4) 清状态表（plugin_state + plugin_setting）
        with get_db() as db:
            st = db.get(PluginState, plugin_id)
            if st is not None:
                db.delete(st)
            for row in db.exec(
                select(PluginSetting).where(PluginSetting.plugin_id == plugin_id)
            ).all():
                db.delete(row)
            db.commit()
        # 5) 删文件（插件目录整体移除）
        if info.directory.exists():
            shutil.rmtree(info.directory, ignore_errors=True)
        return {"id": plugin_id, "uninstalled": True}

    # ───────────────────────── 设置 ─────────────────────────
    def get_settings(self, plugin_id: str) -> dict[str, Any]:
        self._require(plugin_id)
        with get_db() as db:
            return read_settings(db, plugin_id)

    def set_settings(self, plugin_id: str, settings: dict[str, Any]) -> dict[str, Any]:
        info = self._require(plugin_id)
        with get_db() as db:
            return write_settings(db, info, plugin_id, settings)

    # ───────────────────────── 健康 ─────────────────────────
    def health(self, plugin_id: str) -> dict[str, Any]:
        item = self.get_plugin(plugin_id)
        return {
            "id": plugin_id,
            "enabled": item["enabled"],
            "last_error": item["last_error"],
            "ok": item["enabled"] and item["last_error"] is None,
        }


_manager: PluginManager | None = None


def get_plugin_manager() -> PluginManager:
    global _manager
    if _manager is None:
        _manager = PluginManager()
    return _manager
