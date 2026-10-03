"""路由挂载注册表（最小骨架，留给 T14 顶替）。

★ 铁律：必须有 unmount —— 否则"插件可禁用"是空话。
  内核只负责"把 router 挂上去/摘下来"，具体发现/生命周期/权限归 T14。

形状对齐投喂包要求的 RouterHost(Protocol)：
    mount(plugin_id, router, prefix) / unmount(plugin_id) / mounted() -> list[str]
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from fastapi import APIRouter, FastAPI


@runtime_checkable
class RouterHost(Protocol):
    def mount(self, plugin_id: str, router: APIRouter, prefix: str) -> None: ...

    def unmount(self, plugin_id: str) -> None: ...

    def mounted(self) -> list[str]: ...


class ModuleRegistry:
    """内核级路由挂载表。

    - mount：把模块的 APIRouter 挂到 app 上，prefix 由 manifest.api.base 决定。
    - unmount：把该模块挂载产生的所有路由摘掉（支持"禁用"）。
    - mounted：返回当前已挂载的模块 id 列表。
    """

    def __init__(self) -> None:
        self._app: FastAPI | None = None
        self._mounted: dict[str, list[Any]] = {}  # plugin_id -> 它产生的 route 对象

    def bind(self, app: FastAPI) -> None:
        self._app = app

    def mount(self, plugin_id: str, router: APIRouter, prefix: str) -> None:
        if self._app is None:
            raise RuntimeError("ModuleRegistry 未绑定 app，无法挂载")
        if plugin_id in self._mounted:
            raise RuntimeError(f"模块已挂载：{plugin_id}")
        before = len(self._app.routes)
        try:
            self._app.include_router(router, prefix=prefix, tags=[plugin_id])
        except BaseException:
            # ★ ADR-0005（2026-10-03）：include_router 可能**部分写入**后才抛
            #   （prefix 冲突、依赖注入签名错误等）。若就此上抛，这些路由已进
            #   app.routes 却没人登记 → 成为**永远无法 unmount 的孤儿路由**，
            #   "插件可禁用"被击穿。故此处先按对象身份摘掉本次写入的片段再上抛，
            #   保证 mount 失败后 app.routes 与调用前逐元素等价（可逆性）。
            added = self._app.routes[before:]
            if added:
                owned = {id(r) for r in added}
                self._app.router.routes = [
                    r for r in self._app.router.routes if id(r) not in owned
                ]
            raise
        added = self._app.routes[before:]
        self._mounted[plugin_id] = added

    def unmount(self, plugin_id: str) -> None:
        if self._app is None:
            raise RuntimeError("ModuleRegistry 未绑定 app，无法卸载")
        routes = self._mounted.pop(plugin_id, None)
        if routes is None:
            return
        owned = set(id(r) for r in routes)
        # 摘掉该模块产生的路由（用对象身份，不影响其它模块）。
        # 注意：Starlette 的 `app.routes` 是只读 property，要改必须落到 `app.router.routes`。
        self._app.router.routes = [r for r in self._app.router.routes if id(r) not in owned]

    def mounted(self) -> list[str]:
        return list(self._mounted.keys())

    # 兼容 Protocol 命名（也允许属性访问）
    def __call__(self) -> ModuleRegistry:
        return self
