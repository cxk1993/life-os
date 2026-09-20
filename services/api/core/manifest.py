"""模块 manifest 模型 + 自动发现。

★ 这是 T03 的"模块自动发现"职责（总纲 §1.3 / 验收 #2-#3）。
  校验失败必须**明确指出是哪个模块、哪个字段**（不许静默跳过）。
  正式的 plugin.schema.json 归 T14；这里是内核运行期的最小校验。
"""
from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from core.errors import ManifestError

_KINDS = {"core", "builtin", "third-party"}
_ID_RE = __import__("re").compile(r"^[a-z][a-z0-9-]*$")
# TX-ACT-01：activates_on 条目只允许 startup:always 或 event:<topic>
# （topic 点分小写、至少两段，如 event:note.created）——与 contracts/plugin.schema.json
# 的 pattern 保持字面一致，两层校验同一语义。
_ACTIVATES_ON_RE = __import__("re").compile(
    r"^(startup:always|event:[a-z0-9-]+(\.[a-z0-9-]+)+)$"
)


class ManifestApi(BaseModel):
    base: str = Field(..., description="路由前缀，必须为 /api/v1/<id>")
    openapi: str | None = None
    health: str | None = None


class Manifest(BaseModel):
    id: str
    name: str
    version: str
    kind: str
    minKernel: str | None = None
    kernelApi: str | None = None
    icon: str | None = None
    description: str | None = None
    author: str | None = None
    api: ManifestApi
    provides: list[str] = []
    requires: list[str] = []
    slots: list[str] = []
    emits: list[str] = []
    consumes: list[str] = []
    permissions: list[str] = []
    activates_on: list[str] = []
    migrations: str | None = None
    settingsSchema: str | None = None
    lifecycle: dict[str, Any] = Field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)


def _validate(module_id: str, raw: dict[str, Any], dir_name: str) -> Manifest:
    """校验单个 manifest，失败抛 ManifestError（带模块名+字段）。"""
    try:
        m = Manifest(**raw)
    except ValidationError as exc:
        locs = "; ".join(
            f"{'/'.join(str(p) for p in e['loc']) or '<root>'}: {e['msg']}"
            for e in exc.errors()
        )
        raise ManifestError(
            f"模块「{module_id}」manifest 校验失败：{locs}"
        ) from exc

    if m.id != dir_name:
        raise ManifestError(
            f"模块「{dir_name}」manifest.id={m.id!r} 必须等于目录名 {dir_name!r}"
        )
    if not _ID_RE.match(m.id):
        raise ManifestError(
            f"模块「{m.id}」id 必须是小写英文/数字/连字符，且以字母开头"
        )
    if m.kind not in _KINDS:
        raise ManifestError(
            f"模块「{m.id}」kind={m.kind!r} 必须是 {sorted(_KINDS)} 之一"
        )
    expected_base = f"/api/v1/{m.id}"
    if m.api.base != expected_base:
        raise ManifestError(
            f"模块「{m.id}」api.base 必须是 {expected_base!r}，实际为 {m.api.base!r}"
        )
    for act in m.activates_on:
        if not _ACTIVATES_ON_RE.match(act):
            raise ManifestError(
                f"模块「{m.id}」activates_on 条目 {act!r} 非法：只支持 "
                "startup:always 或 event:<topic>（点分小写、至少两段，如 event:note.created）"
            )
    return m


def discover_modules(modules_dir: str | Path) -> list[tuple[Manifest, Path]]:
    """扫描 modules/*/manifest.json，返回 (manifest, 目录) 列表。

    同 id 重复 -> 报错。无 router.py -> 报错。
    """
    root = Path(modules_dir)
    found: dict[str, tuple[Manifest, Path]] = {}
    results: list[tuple[Manifest, Path]] = []

    if not root.is_dir():
        return results

    for sub in sorted(root.iterdir()):
        if not sub.is_dir():
            continue
        manifest_path = sub / "manifest.json"
        if not manifest_path.is_file():
            continue
        try:
            raw = __import__("json").loads(manifest_path.read_text(encoding="utf-8"))
        except __import__("json").JSONDecodeError as exc:
            raise ManifestError(
                f"模块「{sub.name}」manifest.json 不是合法 JSON：{exc}"
            ) from exc

        m = _validate(sub.name, raw, sub.name)
        if m.id in found:
            raise ManifestError(f"模块 id 重复：{m.id!r}（{sub.name} 与已发现模块冲突）")
        found[m.id] = (m, sub)
        results.append((m, sub))

    return results


def load_router(module_id: str) -> Any:
    """动态导入 modules.<id>.router 并取 router 对象。"""
    try:
        mod = importlib.import_module(f"modules.{module_id}.router")
    except ModuleNotFoundError as exc:
        raise ManifestError(
            f"模块「{module_id}」缺少 router.py（无法 import modules.{module_id}.router）：{exc}"
        ) from exc
    router = getattr(mod, "router", None)
    if router is None:
        raise ManifestError(f"模块「{module_id}」router.py 未定义 router = APIRouter()")
    return router
