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

from core.manifest import ManifestError, discover_modules


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
