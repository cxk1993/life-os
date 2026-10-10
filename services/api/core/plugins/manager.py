"""插件管理器（总纲 §1.3 / 验收 B）：install / enable / disable / uninstall / 设置。

★ 注册表(plugin_state)与运行时对象(挂载的 router)分离 —— 这是热插拔的前提，
  也是"一切皆插件"不被腐蚀的结构保障。

职责边界（不抢别人的活）：
  - 发现/校验/版本/权限/迁移/设置/生命周期 分别由同包其它模块负责，这里只编排。
  - 路由挂载/摘掉 交给 core.registry.ModuleRegistry（T03 的 RouterHost）。
  - 数据库表/会话 交给 db（T04）。

★ 可逆性纪律（ADR-0005，2026-10-03）：
  每个 effect 必须携带逆；失败时按「应用的逆序」回放逆（论文 Theorem 16）。
  改动前请自问：这个 effect 的逆是什么？在哪个状态上生效？
"""
from __future__ import annotations

import json
import logging
import shutil
import threading
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

# ★ ADR-0005（2026-10-03）· 启动恢复的退避上限。
#   严守「卡档缓行纪律」：达上限后**不自动禁用、不改 enabled、不摘路由** ——
#   只退避（本轮跳过重试）+ 报警，状态原样保留等人来看。计数是**进程内**的，
#   不落库 —— 否则「跳过」会被固化成事实，插件再也等不到自愈。
_RECOVERY_MAX_CONSECUTIVE = 3

# 启动恢复的进程内追踪（不落库 —— 见上方说明）
_recovery_failures: dict[str, int] = {}
_recovery_last_error: dict[str, str] = {}
_recovery_lock = threading.Lock()


def reset_recovery_tracker() -> None:
    """清空启动恢复追踪（测试与「修复后手动重试成功」两处会调）。"""
    with _recovery_lock:
        _recovery_failures.clear()
        _recovery_last_error.clear()


def note_recovery_attempt(plugin_id: str) -> tuple[bool, int]:
    """报一次启动恢复尝试 → (是否应退避跳过, 已累计连续失败次数)。

    ⚠️ 退避分支里调用方**不得** enable、不得改 enabled、不得摘路由 ——
    卡档缓行纪律：只跳过这一轮，状态原样留着等人。
    """
    with _recovery_lock:
        n = _recovery_failures.get(plugin_id, 0)
        return n >= _RECOVERY_MAX_CONSECUTIVE, n


def note_recovery_result(plugin_id: str, error: str | None) -> None:
    """记一次启动恢复结果：成功清零，失败累加。"""
    with _recovery_lock:
        if error is None:
            _recovery_failures.pop(plugin_id, None)
            _recovery_last_error.pop(plugin_id, None)
        else:
            _recovery_failures[plugin_id] = _recovery_failures.get(plugin_id, 0) + 1
            _recovery_last_error[plugin_id] = error


def recovery_backoff_snapshot() -> dict[str, tuple[int, str]]:
    """退避状态只读快照（供 readyz / 测试查看）。"""
    with _recovery_lock:
        return {
            k: (v, _recovery_last_error.get(k, ""))
            for k, v in _recovery_failures.items()
        }

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
            # 口径统一（2026-09-27 · 主人件①）：无状态行的默认启用态按来源判——
            # builtin/core 随系统发布默认在用；third-party 从未动过 = 未启用
            #（ADR-0002「可禁用」语义的权威态，与 core/app.py 启动恢复同规则）。
            # 旧值恒 True 会造成「MCP 工具已暴露 / 路由未挂载」的幽灵工具
            #（countdown 404 根因之一）。
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
    # 挂载统一走 core.plugins.discover.mount_plugin（前置小步：
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
            #
            # ★ 差分必须**延迟到补偿时**才计算：run_migrations 若中途失败
            #（如 0001 成功、0002 抛错），`after_versions` 那行根本不会执行，
            #   提前算出的差分会漏掉已执行的 0001。故 lambda 在 undo 时才取
            #   「当前台账 − before」，捕获真正落库的那些版本。
            # ★ 逆必须**先于 effect 注册**（2026-10-03 踩过）：
            #   run_migrations 若中途失败（0001 建表成功、0002 抛错），它之后的
            #   语句根本不会执行 —— 若把 _record 放在它后面，逆就没被登记，
            #   补偿时无从回放，0001 建的表会永久残留。故先把「回滚到 before
            #   台账」登记好，再施加 effect。
            before_versions = recorded_versions(engine, info.id)
            _record(
                "migrations",
                lambda: rollback_versions(
                    engine,
                    info,
                    sorted(recorded_versions(engine, info.id) - before_versions),
                ),
            )
            run_migrations(engine, info)

            mount_plugin(info, registry)
            _record("mount", lambda: self._unmount(info, registry))

            with db_session() as db:
                err = run_lifecycle_hook(info, "enable", db=db)
        except Exception as exc:  # noqa: BLE001
            self._compensate(done, info, exc)
            # 补偿已把状态恢复到调用前（含"原先无行则删行"）。此后只做目击：
            #   - 调用前本就是启用态（重调边界）→ **保持启用**，仅把错误写进 last_error
            #（绝不能顺手改成 disabled —— 那是一次计划外的副作用）；
            #   - 否则建/改成 enabled=False 并记错误，留下可诊断的行。
            #
            # ★ 注意：本分支不会因「生命周期钩子抛异常」而进 —— run_lifecycle_hook
            #   自己吞异常并返回错误串（见 lifecycle.py），钩子失败是**软失败**，
            #   走下方 `if err:` 分支（不回滚，语义同旧实现）。
            if prev_state and prev_state.get("enabled"):
                self.note_activation_error(plugin_id, str(exc))
            else:
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
        # 校验权限声明合法（★ 2026-09-25 先归一化，兼容对象格式）
        #
        # ★ ADR-0005（2026-10-03）：这里**只做结构校验**（拒绝非法权限串）。
        #   真正的授权决策在 uninstall 前的审批环节 —— 对应论文 §6.3 的
        #   capability request：请求应在**组件运行前**被审阅批准，而非运行时才发现。
        for perm in normalize_permissions(info.manifest.get("permissions")):
            if not is_valid_permission(perm):
                raise ForbiddenError(f"插件「{plugin_id}」声明了非法权限：{perm!r}")

        # ★ ADR-0005 · 可逆安装：effect 必须携带逆，失败按逆序回放。
        #
        # 旧实现与 enable() 同病 —— 四个 effect 全都没有逆：
        #   [建表 → on_install → 状态落 enabled=True → 挂路由]
        # 任何一步失败都会留下中间态：表建了、钩子跑了、状态说已启用，但路由不在，
        # 且前端「安装」按钮看到的是一次 500 —— 再点一次会撞上已存在的表。
        #
        # 现按论文 §3.1 建模（与 enable() 同一 accumulator 纪律）：
        #   done 累积已生效 effect 的逆，异常时 reversed(done) 逆序回放（Theorem 16）。
        #   补偿自身失败只记日志、绝不上抛 —— 不许掩盖原始异常。
        #
        # ⚠️ 与 enable() 的一处不同：install 的迁移逆用**全量** rollback（newly_run
        #   只是防御性限定），因为 install 的语义是「首次安装」—— 理论上无历史迁移，
        #   且 uninstall 本就是全量 rollback_migrations（见其第 3 步）。语义一致。
        #   enable() 则必须用差分（那里的插件可能已存在并有历史数据）。
        prev_state = self._state_snapshot(plugin_id)
        done: list[tuple[str, Any]] = []

        def _record(name: str, undo: Any) -> None:
            done.append((name, undo))

        try:
            from db.engine import get_engine

            engine = get_engine()

            # ★ 逆必须**先于 effect 注册**（2026-10-03 踩过）：
            #   run_migrations 若中途失败（0001 建表成功、0002 抛错），它之后的
            #   语句根本不会执行 —— 若把 _record 放在它后面，逆就没被登记，
            #   补偿时无从回放，0001 建的表会永久残留。故先把「回滚到 before
            #   台账」登记好，再施加 effect。
            before_versions = recorded_versions(engine, info.id)
            _record(
                "migrations",
                lambda: rollback_versions(
                    engine,
                    info,
                    sorted(recorded_versions(engine, info.id) - before_versions),
                ),
            )
            run_migrations(engine, info)

            with db_session() as db:
                run_lifecycle_hook(info, "install", db=db)
            # 钩子的逆是与它配对的 teardown。run_lifecycle_hook 对
            # 「钩子缺失/不抛」一律 best-effort 吞掉（见 lifecycle.py），故这里
            # 无 on_uninstall 时是无害 no-op —— 与 uninstall() 第 1 步同一调用。
            _record(
                "install_hook",
                lambda: self._run_hook_safe(info, "uninstall"),
            )

            self._upsert_state(info, enabled=True, last_error=None)
            _record("state", lambda: self._restore_state(plugin_id, prev_state))

            mount_plugin(info, registry)
            _record("mount", lambda: self._unmount(info, registry))
        except Exception as exc:  # noqa: BLE001
            # 逆序回滚全部已生效 effect（含删表、删状态行）。
            self._compensate(done, info, exc)
            # 目击：install 失败 = 回到"未安装"，**不新建状态行**（与 uninstall 后的
            # vacant 态一致）。仅当原先就有行（重装边界）时保留该行并记下错误。
            if prev_state is not None:
                self.note_activation_error(plugin_id, str(exc))
            raise
        return self.get_plugin(plugin_id)

    def _run_hook_safe(self, info: PluginInfo, stage: str) -> None:
        """在补偿路径上跑钩子：自己吞异常（补偿绝不允许二次上抛）。"""
        try:
            with db_session() as db:
                run_lifecycle_hook(info, stage, db=db)
        except Exception as hook_exc:  # noqa: BLE001
            log.warning(
                "插件补偿钩子执行失败",
                extra={
                    "module": info.id,
                    "stage": stage,
                    "error": f"{type(hook_exc).__name__}: {hook_exc}",
                },
            )

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
