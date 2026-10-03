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

from core.deps import db_session
from core.errors import ConflictError, ForbiddenError, NotFoundError
from core.plugins import discover as discover_mod
from core.plugins.discover import DiscoveryResult, PluginInfo, mount_plugin
from core.plugins.lifecycle import run_lifecycle_hook
from core.plugins.migrations import (
    recorded_versions,
    rollback_migrations,
    rollback_versions,
    run_migrations,
)
from core.plugins.permissions import is_valid_permission, normalize_permissions
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
        with db_session() as db:
            states = {
                s.id: s
                for s in db.exec(select(PluginState)).all()
            }
        out: list[dict[str, Any]] = []
        for p in result.plugins:
            st = states.get(p.id)
            # 口径统一（2026-09-27 · 主人令件①）：无状态行的默认启用态按来源判——
            # builtin/core 随系统发布默认在用；third-party 从未动过 = 未启用
            # （ADR-0002「可禁用」语义的权威态，与 core/app.py 启动恢复同规则）。
            # 旧值恒 True 会造成「MCP 工具已暴露 / 路由未挂载」的幽灵工具
            # （countdown 404 根因之一）。
            enabled = st.enabled if st is not None else p.source != "third-party"
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
                    # ★ ISSUE-012（2026-09-23 hermes）：清单必须携带完整 manifest，
                    #   否则前端 `p.manifest.entry/window/slots` 必崩，插件扩展点贡献
                    #   结构化无法挂载（E5 sidecar / D1 dashboard.card / DEG-01 软依赖角标）。
                    "manifest": p.manifest,
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
                        "enabled": self._enabled(p.id, default_enabled=p.source != "third-party"),
                    }
                )
        return out

    def _enabled(self, plugin_id: str, *, default_enabled: bool = True) -> bool:
        with db_session() as db:
            st = db.get(PluginState, plugin_id)
        return st.enabled if st else default_enabled

    # ───────────────────────── 状态落库 ─────────────────────────
    def _upsert_state(
        self,
        info: PluginInfo,
        *,
        enabled: bool,
        last_error: str | None = None,
    ) -> None:
        manifest = info.manifest
        granted = normalize_permissions(manifest.get("permissions"))
        with db_session() as db:
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

    def note_activation_error(self, plugin_id: str, error: str | None) -> None:
        """写激活器目击到 plugin_state.last_error（ADR-0005 落库通道的宿主侧）。

        由 core/app.py 注入给 PluginActivator.set_persist_hook。状态行不存在时
        不新建 —— 激活器只对**已有注册态**的插件报错，凭空建行会让
        list_plugins 的「无状态行 ⇒ 按来源取默认」口径漂移。
        """
        with db_session() as db:
            st = db.get(PluginState, plugin_id)
            if st is None:
                return
            st.last_error = error
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

        # ★ ADR-0005（2026-10-03）· 可逆启用：effect 必须携带逆，失败按逆序回放。
        #
        # 旧实现是「部分提交」：状态先落 enabled=True，再跑迁移（失败静默吞），
        # 再挂路由（失败只记 last_error 后上抛）。三个 effect 全都没有逆，于是
        # 失败后留下**状态说已启用、路由却不在**的中间态 —— 这正是主人实盘见过
        # 的「路由全 404 但工具在列」。且 core/app.py 的启动恢复只读 enabled、
        # 不看 last_error，于是每次重启重试、每次重复半提交。
        #
        # 现按论文 §3.1 建模：done 是 accumulator（累积已生效 effect 的逆），
        # 异常时 reversed(done) 逆序回放（Theorem 16：逆必须按应用的逆序施加）。
        # 补偿自身失败只记日志、绝不上抛 —— 不许掩盖原始异常。
        prev_state = self._state_snapshot(plugin_id)
        done: list[tuple[str, Any]] = []  # [(effect 名, 逆操作)]

        def _record(name: str, undo: Any) -> None:
            done.append((name, undo))

        try:
            self._upsert_state(info, enabled=True, last_error=None)
            _record("state", lambda: self._restore_state(plugin_id, prev_state))

            from db.engine import get_engine

            engine = get_engine()

            # 迁移：逆是「只回滚本次真正执行的那几个版本」。台账幂等，故先取
            # 差分；绝不能调全量 rollback_migrations（会 drop 掉承载历史数据的表）。
            before_versions = recorded_versions(engine, info.id)
            run_migrations(engine, info)
            after_versions = recorded_versions(engine, info.id)
            newly_run = after_versions - before_versions
            _record(
                "migrations",
                lambda: rollback_versions(engine, info, sorted(newly_run)),
            )

            mount_plugin(info, registry)
            _record("mount", lambda: self._unmount(info, registry))

            with db_session() as db:
                err = run_lifecycle_hook(info, "enable", db=db)
        except Exception as exc:  # noqa: BLE001
            self._compensate(done, info, exc)
            self._upsert_state(info, enabled=False, last_error=str(exc))
            raise
        if err:
            # 钩子未抛异常、只回报了错误串：效果已生效（不回滚，语义同旧实现），
            # 仅把错误落到 last_error 供 health/readyz 目击。
            self._upsert_state(info, enabled=True, last_error=err)
        return self.get_plugin(plugin_id)

    def _compensate(
        self, done: list[tuple[str, Any]], info: PluginInfo, exc: BaseException
    ) -> None:
        """逆序回放已生效 effect 的逆（Theorem 16）。补偿失败只记，不上抛。"""
        for name, undo in reversed(done):
            try:
                undo()
            except Exception as undo_exc:  # noqa: BLE001 —— 不许掩盖原始异常
                log.warning(
                    "插件启用补偿失败（已记录，不掩盖原始异常）",
                    extra={
                        "module": info.id,
                        "step": name,
                        "original": f"{type(exc).__name__}: {exc}",
                        "undo_error": f"{type(undo_exc).__name__}: {undo_exc}",
                    },
                )

    def _state_snapshot(self, plugin_id: str) -> dict[str, Any] | None:
        """取插件状态行的可恢复快照（无行时为 None）。"""
        with db_session() as db:
            st = db.get(PluginState, plugin_id)
            if st is None:
                return None
            return {
                "version": st.version,
                "kind": st.kind,
                "enabled": st.enabled,
                "last_error": st.last_error,
                "granted_permissions": st.granted_permissions,
            }

    def _restore_state(self, plugin_id: str, snapshot: dict[str, Any] | None) -> None:
        """把状态行恢复到快照值；原先无行则删除该行（完整回滚）。"""
        with db_session() as db:
            st = db.get(PluginState, plugin_id)
            if snapshot is None:
                if st is not None:
                    db.delete(st)
                    db.commit()
                return
            if st is None:
                st = PluginState(id=plugin_id)
                db.add(st)
            st.version = snapshot["version"]
            st.kind = snapshot["kind"]
            st.enabled = snapshot["enabled"]
            st.last_error = snapshot["last_error"]
            st.granted_permissions = snapshot["granted_permissions"]
            db.commit()

    def disable(self, plugin_id: str, registry: Any) -> dict[str, Any]:
        info = self._require(plugin_id)
        if info.kind == "core":
            raise ForbiddenError(f"内核插件「{plugin_id}」不可禁用（kind=core）")
        # ★ ADR-0005（2026-10-03）：逆序。加载顺序是
        #     [迁移 → 挂路由 → on_enable]，卸载必须严格逆序：
        #     [on_disable → 摘路由 → (迁移回滚)]
        #   旧实现先 _unmount 再跑 on_disable —— 插件撤自己的东西时，它的路由
        #   已经消失了（顺序反了）。迁移回滚仍留在 uninstall：disable 的语义是
        #   「停用」不是「删数据」，表要留着等下次 enable（run_migrations 台账
        #   幂等，不会重跑也不会丢数据）。
        with db_session() as db:
            err = run_lifecycle_hook(info, "disable", db=db)
        self._unmount(info, registry)
        self._upsert_state(info, enabled=False, last_error=err)
        return self.get_plugin(plugin_id)

    # ───────────────────────── 安装 / 卸载（仅 third-party） ─────────────────────────
    def install(self, plugin_id: str, registry: Any) -> dict[str, Any]:
        info = self._require(plugin_id)
        if info.kind in ("core", "builtin"):
            raise ConflictError(
                f"插件「{plugin_id}」是 {info.kind}，{_BUILTIN_INCLUSION_NOTE}"
            )
        # 校验权限声明合法（★ 2026-09-25 TX-FRAME-01：先归一化，兼容对象格式）
        for perm in normalize_permissions(info.manifest.get("permissions")):
            if not is_valid_permission(perm):
                raise ForbiddenError(f"插件「{plugin_id}」声明了非法权限：{perm!r}")
        # 建表
        from db.engine import get_engine

        engine = get_engine()
        run_migrations(engine, info)
        with db_session() as db:
            run_lifecycle_hook(info, "install", db=db)
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
        with db_session() as db:
            run_lifecycle_hook(info, "uninstall", db=db)
        # 2) 摘掉路由（扩展点注册清理）
        self._unmount(info, registry)
        # 3) 回滚迁移（删表）
        from db.engine import get_engine

        engine = get_engine()
        rollback_migrations(engine, info)
        # 4) 清状态表（plugin_state + plugin_setting）
        with db_session() as db:
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
        with db_session() as db:
            return read_settings(db, plugin_id)

    def set_settings(self, plugin_id: str, settings: dict[str, Any]) -> dict[str, Any]:
        info = self._require(plugin_id)
        with db_session() as db:
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
