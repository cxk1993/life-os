"""TX-DEG-01 · 依赖声明闸门测试（#033 四条静态规则）。

★ 语义锚点：`requires` / `optionalDependencies` 里写的是**能力名**（如 web.entry.read），
  **不是模块 id** —— 判据为「该能力必须被某个模块 provides」。此语义在实装时被真实
  目录（catalog 依赖 web 的能力）打回后校准。

方式：造临时模块目录（tmp_path）→ 调 discover_modules → 断言闸门行为；不碰真 modules/。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.manifest import (
    Manifest,
    ManifestApi,
    ManifestError,
    dependency_status,
    discover_modules,
)


def _manifest(mid: str, **extra: object) -> Manifest:
    """直接构造 Manifest 对象（用于第二部分的纯函数判定测试）。"""
    base: dict[str, object] = {
        "id": mid,
        "name": mid,
        "version": "0.1.0",
        "kind": "builtin",
        "api": ManifestApi(base=f"/api/v1/{mid}"),
        **extra,
    }
    return Manifest(**base)  # type: ignore[arg-type]


def _write(root: Path, mid: str, **extra: object) -> None:
    """炮制一个最小合法模块目录（只要 manifest.json 即会被发现）。"""
    d = root / mid
    d.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, object] = {
        "id": mid,
        "name": mid,
        "version": "0.1.0",
        "kind": "builtin",
        "api": {"base": f"/api/v1/{mid}"},
        **extra,
    }
    (d / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


# ── 基线：合法声明通过 ────────────────────────────────────────────────
def test_valid_capability_deps_pass(tmp_path: Path) -> None:
    _write(tmp_path, "alpha", provides=["alpha.read"])
    _write(tmp_path, "beta", requires=["alpha.read"])
    assert len(discover_modules(tmp_path)) == 2


def test_modules_without_declarations_still_pass(tmp_path: Path) -> None:
    """零声明的存量模块不受新闸门影响（向后兼容，不破现有 18 模块）。"""
    for mid in ("alpha", "beta", "gamma"):
        _write(tmp_path, mid)
    assert len(discover_modules(tmp_path)) == 3


# ── 规则①：依赖的能力必须被某模块 provides ────────────────────────────
def test_rule1_hard_dep_unknown_capability_rejected(tmp_path: Path) -> None:
    _write(tmp_path, "alpha", requires=["ghost.read"])
    with pytest.raises(ManifestError, match="没有任何模块 provides"):
        discover_modules(tmp_path)


def test_rule1_soft_dep_unknown_capability_rejected(tmp_path: Path) -> None:
    _write(tmp_path, "alpha", optionalDependencies=["ghost.read"])
    with pytest.raises(ManifestError, match="optionalDependencies"):
        discover_modules(tmp_path)


# ── 规则②：禁止反向依赖内核内部能力 ──────────────────────────────────
def test_rule2_kernel_internal_capability_rejected(tmp_path: Path) -> None:
    _write(tmp_path, "alpha", requires=["core.internal_thing"])
    with pytest.raises(ManifestError, match="内核内部能力"):
        discover_modules(tmp_path)


# ── 规则③：循环依赖（能力 → 提供者模块，只沿硬依赖）──────────────────
def test_rule3_hard_capability_cycle_rejected(tmp_path: Path) -> None:
    _write(tmp_path, "alpha", provides=["a.read"], requires=["b.read"])
    _write(tmp_path, "beta", provides=["b.read"], requires=["a.read"])
    with pytest.raises(ManifestError, match="循环硬依赖"):
        discover_modules(tmp_path)


def test_rule3_longer_cycle_rejected(tmp_path: Path) -> None:
    _write(tmp_path, "a", provides=["a.cap"], requires=["b.cap"])
    _write(tmp_path, "b", provides=["b.cap"], requires=["c.cap"])
    _write(tmp_path, "c", provides=["c.cap"], requires=["a.cap"])
    with pytest.raises(ManifestError, match="循环硬依赖"):
        discover_modules(tmp_path)


def test_rule3_soft_dependency_cycle_allowed(tmp_path: Path) -> None:
    """★ 软依赖不参与环检测：缺了不死，不构成启动期环（这正是软依赖的意义）。"""
    _write(tmp_path, "alpha", provides=["a.read"], optionalDependencies=["b.read"])
    _write(tmp_path, "beta", provides=["b.read"], optionalDependencies=["a.read"])
    assert len(discover_modules(tmp_path)) == 2


def test_rule3_self_provided_capability_is_not_a_cycle(tmp_path: Path) -> None:
    """依赖自己 provides 的能力不构成环。"""
    _write(tmp_path, "alpha", provides=["a.read"], requires=["a.read"])
    assert len(discover_modules(tmp_path)) == 1


# ── 规则④：软硬互斥 ──────────────────────────────────────────────────
def test_rule4_same_capability_cannot_be_both_soft_and_hard(tmp_path: Path) -> None:
    _write(tmp_path, "alpha", provides=["a.read"])
    _write(tmp_path, "beta", requires=["a.read"], optionalDependencies=["a.read"])
    with pytest.raises(ManifestError, match="软硬必须互斥"):
        discover_modules(tmp_path)


# ── 回归：既有闸门未被破坏 ───────────────────────────────────────────
def test_existing_id_vs_dirname_rule_still_holds(tmp_path: Path) -> None:
    d = tmp_path / "alpha"
    d.mkdir(parents=True)
    (d / "manifest.json").write_text(
        json.dumps(
            {
                "id": "not-alpha",
                "name": "x",
                "version": "0.1.0",
                "kind": "builtin",
                "api": {"base": "/api/v1/not-alpha"},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ManifestError, match="必须等于目录名"):
        discover_modules(tmp_path)


# ══════════ TX-DEG-01 第二部分：软依赖缺失的运行时判定（degraded 半边）══════════
# 硬依赖缺失 = 启动期 fail-fast（运行时不会出现）；运行期只判软依赖。


def test_dependency_status_ok_when_no_soft_deps() -> None:
    st = dependency_status(_manifest("a"), set())
    assert st.state == "ok"
    assert st.reason_code is None
    assert st.missing == ()


def test_dependency_status_ok_when_soft_deps_all_available() -> None:
    m = _manifest("a", optionalDependencies=["x.read", "y.read"])
    st = dependency_status(m, {"x.read", "y.read", "z.read"})
    assert st.state == "ok"
    assert st.reason_code is None


def test_dependency_status_degraded_when_soft_dep_missing() -> None:
    m = _manifest("a", optionalDependencies=["x.read", "y.read"])
    st = dependency_status(m, {"x.read"})  # y.read 缺失
    assert st.state == "degraded"
    assert st.reason_code == "optional_dependency_missing:y.read"
    assert st.missing == ("y.read",)


def test_dependency_status_reason_code_lists_all_missing_sorted() -> None:
    """多条缺失时 reason_code 按字典序全列（供 O1 面板直接展示）。"""
    m = _manifest("a", optionalDependencies=["zeta.read", "alpha.read", "mid.read"])
    st = dependency_status(m, set())
    assert st.state == "degraded"
    assert st.reason_code == "optional_dependency_missing:alpha.read,mid.read,zeta.read"
    assert st.missing == ("alpha.read", "mid.read", "zeta.read")


def test_dependency_status_ignores_hard_deps() -> None:
    """★ 硬依赖不参与运行期判定（缺失已在启动期 fail-fast，不能重复语义）。"""
    m = _manifest("a", requires=["hard.read"])
    st = dependency_status(m, set())  # hard.read 不在可用集
    assert st.state == "ok", "硬依赖缺失不该在运行期被判 degraded"


# ══════════ D′（2026-09-23）：唯一读法之内核侧 + 未知字段必须被报告 ══════════


def test_unknown_field_rejected_for_builtin(tmp_path: Path) -> None:
    """★ 反例（就是讨论第二轮的原始 bug）：内置插件把 requires 拼成 requiers。

    旧行为：**构造成功、零报错、requires 静默为空**（作者以为声明了硬依赖）。
    新行为：当场抛 ManifestError。
    """
    _write(tmp_path, "alpha", requiers=["typo_field"])  # 故意拼错
    with pytest.raises(ManifestError, match="不认识的字段"):
        discover_modules(tmp_path)


def test_unknown_field_allowed_but_reported_for_third_party(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """第三方插件：未知字段**报告但继续**（对齐 Agent Plugins「未知字段 MUST report」）。"""
    _write(tmp_path, "ext", kind="third-party", someFutureField=123)
    with caplog.at_level("WARNING", logger="kernel.manifest"):
        mods = discover_modules(tmp_path)
    assert len(mods) == 1, "第三方插件不该因未知字段被拒"
    assert any("未知字段" in str(r.getMessage()) for r in caplog.records), (
        "必须留下 warning 记录（报告，而非静默吞）"
    )


def test_x_prefix_and_extensions_are_explicit_escape_hatches(tmp_path: Path) -> None:
    """留扩展位：`x_` 前缀与 `extensions` 对象一律放行（不报不拒）。"""
    _write(tmp_path, "alpha", x_custom="anything", extensions={"com.example": {"k": 1}})
    assert len(discover_modules(tmp_path)) == 1


def test_entry_and_window_are_now_visible_to_the_model(tmp_path: Path) -> None:
    """★ D′-1：`entry` / `window` 补进模型 —— 此前它们被静默吞掉（原文通道才看得见）。"""
    _write(tmp_path, "app", entry="@apps/app", window={"w": 720, "h": 520})
    mods = discover_modules(tmp_path)
    m = mods[0][0]
    assert m.entry == "@apps/app"
    assert m.window == {"w": 720, "h": 520}


def test_real_modules_still_all_pass_with_new_gates() -> None:
    """★ 硬判据：18 个真实模块必须在新闸门下**全部通过**（补字段+分档报告不误杀）。"""
    api_root = Path(__file__).resolve().parents[1]
    mods = discover_modules(api_root / "modules")
    assert len(mods) == 18, f"真实模块数变了：{len(mods)}"
