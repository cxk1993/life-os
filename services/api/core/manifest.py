"""模块 manifest 模型 + 自动发现。

★ 这是 T03 的"模块自动发现"职责（总纲 §1.3 / 验收 #2-#3）。
  校验失败必须**明确指出是哪个模块、哪个字段**（不许静默跳过）。
  正式的 plugin.schema.json 归 T14；这里是内核运行期的最小校验。
"""
from __future__ import annotations

import importlib
from collections.abc import Collection
from dataclasses import dataclass
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
    # ISSUE-008 方案 A（2026-09-20）：resource → 真实路由段 的显式映射。
    # 键 = provides 倒数第二段（resource），值 = api.base 下的路由段（如
    # "/entries"、"/health-of-system"）。声明则 MCP 转发用它，未声明的
    # resource 走机械「resource+s」推导——T18「加工具零额外声明」对
    # 常规 REST 资源依旧成立，显式声明只用于不规则/语义命名路由。
    tools: dict[str, str] = {}


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
    # ★ TX-DEG-01（#009 软依赖声明的静态半边）：缺了**不阻塞启动**的依赖。
    #   语义：硬依赖（requires）缺 = 起不来（T14 fail-fast 不变）；
    #        软依赖（本字段）缺 = 坞位挂 degraded 角标，功能降级但不死。
    #   与 requires 必须互斥（同一条目不得两处都写 —— #033 闸门规则 ④）。
    optionalDependencies: list[str] = []
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


# ── TX-DEG-01 · 依赖声明闸门（#033 四条静态规则）─────────────────────────
# 依据：Home Assistant hassfest「Reject manifest dependencies on core integrations」
# （PR #169425）+ 我方显式声明线（#019→#021→#020）。**依赖声明错误必须在闸门层
# 拦截，不能留给运行时** —— 等加载期撞墙时模块已经挂了一半，现场很难定位。
#
# ★ 语义锚点（2026-09-23 实装时被真实目录打回后校准）：`requires` /
#   `optionalDependencies` 里写的是**能力名**（如 `web.entry.read`），**不是模块 id** ——
#   闸门判据是「该能力必须被某个模块 provides」。第一版按"模块 id 必须实存"判，
#   上线即被 catalog（它依赖的是 web 的能力，不是 web 这个模块）拦下 ——
#   这次校准本身就是闸门价值的证明。
#
# 四条规则：① 依赖的能力必须被某模块 provides ② 禁止反向依赖内核内部能力
#           ③ 循环依赖检测（能力→提供者模块，只沿硬依赖）④ 软依赖不得同时是硬依赖
KERNEL_RESERVED_CAPABILITY_PREFIXES: tuple[str, ...] = ("core.", "kernel.", "_kernel.")


def _gate_dependency_declarations(found: dict[str, tuple[Manifest, Path]]) -> None:
    """依赖声明闸门：全部模块发现后统一校验，失败抛 ManifestError（启动即失败）。"""
    # 能力名 → 提供者模块 id
    provider: dict[str, str] = {}
    for mid, (m, _p) in found.items():
        for cap in m.provides:
            provider.setdefault(cap, mid)

    # 模块 → 其硬依赖所指向的模块（经「能力 → 提供者」映射；软依赖不入图）
    hard_edges: dict[str, set[str]] = {mid: set() for mid in found}

    for mid, (m, _p) in found.items():
        hard, soft = list(m.requires), list(m.optionalDependencies)

        # ④ 软硬互斥（同一能力不得两处都写）
        both = sorted(set(hard) & set(soft))
        if both:
            raise ManifestError(
                f"模块「{mid}」的能力 {both} 同时出现在 requires 与 optionalDependencies"
                "（软硬必须互斥：要么缺了会死，要么缺了降级，不能两头都占）"
            )

        for cap in hard + soft:
            field = "requires" if cap in hard else "optionalDependencies"
            # ② 不得反向依赖内核内部能力
            if cap.startswith(KERNEL_RESERVED_CAPABILITY_PREFIXES):
                raise ManifestError(
                    f"模块「{mid}」{field} 依赖内核内部能力 {cap!r}"
                    "（内核是宿主、不对外 provides —— 反向依赖禁止）"
                )
            # ① 依赖的能力必须真的有人 provides
            if cap not in provider:
                raise ManifestError(
                    f"模块「{mid}」{field} 声明的能力 {cap!r} 没有任何模块 provides"
                )
            if field == "requires":
                owner = provider[cap]
                if owner != mid:  # 依赖自己提供的能力不构成环
                    hard_edges[mid].add(owner)

    # ③ 循环依赖：沿「能力 → 提供者模块」的硬边遍历（软依赖缺了不死，不参与）
    white, gray, black = 0, 1, 2
    color: dict[str, int] = dict.fromkeys(found, white)

    def visit(node: str, path: list[str]) -> None:
        color[node] = gray
        for nxt in sorted(hard_edges.get(node, ())):
            if nxt not in found:  # 规则①已拦，此处防御性跳过
                continue
            if color[nxt] == gray:
                raise ManifestError("检测到循环硬依赖：" + " → ".join([*path, node, nxt]))
            if color[nxt] == white:
                visit(nxt, [*path, node])
        color[node] = black

    for mid in sorted(found):
        if color[mid] == white:
            visit(mid, [])


# ── TX-DEG-01 · 软依赖缺失的运行时判定（#009 的 degraded 半边）────────────
# 硬依赖缺失 = 启动期 fail-fast（T14 语义），**运行时不会出现** —— 所以运行期只判软依赖。
# 产出 degraded + reason_code，供 O1 四态面板消费（#009：「增加 reason_code 字段即可
# 对齐，不动 schema 主结构」）。
#
# health / O1 侧接入示例（无需改本模块即可用）：
#     avail = {cap for m, _ in discovered for cap in m.provides}
#     st = dependency_status(manifest, avail)
#     # st.state ∈ {"ok", "degraded"}
#     # st.reason_code 形如 "optional_dependency_missing:finance.beeccount.read"
@dataclass(frozen=True)
class DependencyStatus:
    """模块依赖态判定结果（运行期；只覆盖软依赖半边）。"""

    state: str  # "ok" | "degraded"
    reason_code: str | None
    missing: tuple[str, ...]


def dependency_status(m: Manifest, available: Collection[str]) -> DependencyStatus:
    """按软依赖声明 + 当前可用能力集合，判定模块依赖态。

    ★ 只判软依赖（`optionalDependencies`）：硬依赖缺失已由启动期 fail-fast 拦下，
      运行期不会出现 —— 此处不重复判定，避免两处语义打架。
    """
    missing = tuple(sorted(c for c in m.optionalDependencies if c not in available))
    if not missing:
        return DependencyStatus(state="ok", reason_code=None, missing=())
    return DependencyStatus(
        state="degraded",
        reason_code="optional_dependency_missing:" + ",".join(missing),
        missing=missing,
    )


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

    # ★ TX-DEG-01：全部发现后统一过「依赖声明闸门」（①实存 ②禁内核 ③环 ④软硬互斥）
    _gate_dependency_declarations(found)

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
