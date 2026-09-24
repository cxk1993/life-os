#!/usr/bin/env python
"""能力依赖图导出（提案 C 的数据侧）—— 给 catalog 依赖图视图 / 任何可视化消费。

★ 来源：TX-DEG-01 的依赖闸门（`core/manifest.py::_gate_dependency_declarations`）
  内部已经建立了「能力名 → 提供者模块」的完整映射 —— 那份数据**现在只用来拦错**，
  用完就丢。本工具把它**导出来**，让"谁依赖谁"可以被看见。

输出结构（JSON）：
{
  "generated_at": "...",
  "modules": [
    {"id": "todo", "provides": [...], "requires": [...], "optional": [...],
     "hard_providers": ["calendar"], "soft_providers_missing": []}
  ],
  "edges": [ {"from": "todo", "to": "calendar", "kind": "hard", "via": "calendar.event.read"} ],
  "singles": {"single_point": ["calendar"], "isolated": ["diary"], "degraded": []}
}

用途：
- catalog「依赖关系」视图的数据源（提案 C 前端侧，视图归 Doubao）
- 审计：一眼看出单点模块 / 孤岛模块 / 软依赖缺口

用法：
    python tools/export_capability_map.py                      # stdout
    python tools/export_capability_map.py --json out.json      # 落盘
零第三方依赖；只读（discover_modules 不写任何东西）。
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "api"))

from core.manifest import Manifest, dependency_status, discover_modules  # noqa: E402

MODULES_DIR = Path(__file__).resolve().parents[1] / "services" / "api" / "modules"


def build(modules_dir: Path) -> dict:
    mods = discover_modules(modules_dir)
    manifests: list[Manifest] = [m for m, _ in mods]

    # 能力名 → 提供者模块（与内核闸门同一套映射逻辑）
    provider: dict[str, str] = {}
    for m in manifests:
        for cap in m.provides:
            provider.setdefault(cap, m.id)
    available = set(provider)

    modules_out: list[dict] = []
    edges: list[dict] = []
    soft_missing_all: list[dict] = []

    hard_edges: dict[str, set[str]] = {m.id: set() for m in manifests}

    for m in manifests:
        hard_providers: list[str] = []
        soft_missing: list[str] = []
        for cap in m.requires:
            owner = provider.get(cap)
            if owner and owner != m.id:
                hard_edges[m.id].add(owner)
                hard_providers.append(owner)
        for cap in m.optionalDependencies:
            owner = provider.get(cap)
            if owner is None:
                soft_missing.append(cap)
        if soft_missing:
            soft_missing_all.append({"id": m.id, "missing": sorted(soft_missing)})

        modules_out.append(
            {
                "id": m.id,
                "kind": m.kind,
                "provides": sorted(m.provides),
                "requires": sorted(m.requires),
                "optional": sorted(m.optionalDependencies),
                "hard_providers": sorted(set(hard_providers)),
                "soft_providers_missing": sorted(soft_missing),
            }
        )

    for m in manifests:
        for cap in m.requires:
            owner = provider.get(cap)
            if owner and owner != m.id:
                edges.append(
                    {"from": m.id, "to": owner, "kind": "hard", "via": cap}
                )
        for cap in m.optionalDependencies:
            owner = provider.get(cap)
            if owner and owner != m.id:
                edges.append(
                    {"from": m.id, "to": owner, "kind": "soft", "via": cap}
                )

    # 三类审计点
    depended: dict[str, int] = defaultdict(int)
    for e in edges:
        if e["kind"] == "hard":
            depended[e["to"]] += 1
    single_point = sorted(k for k, v in depended.items() if v >= 3)  # ≥3 个模块硬依赖它
    has_deps = {e["from"] for e in edges}
    isolated = sorted(m.id for m in manifests if m.id not in has_deps and not any(
        e["to"] == m.id for e in edges
    ))

    # ★ U2（2026-09-24 · 副总监拍案 1 号）：today-summary 提供者审计
    #   约定：插件在 manifest `provides` 里声明 `x.summary.today` = 本插件提供
    #   `GET /api/v1/<id>/today-summary`（规范见 docs/specs/today-summary数据源规范-v1.md）。
    #   声明走 provides（已知字段，D′ 后模型可见；能力名非顶层字段，不触 extra 分档）。
    summary_providers = sorted(
        m.id for m in manifests if "x.summary.today" in m.provides
    )

    # ★ U3 dock 过载守门（dock数据源规范 v1 §4）：两侧合计 >6 卡 → 提示重审信息架构
    dock_cards = [
        {"id": m.id, "slot": s}
        for m in manifests
        for s in m.slots
        if s.startswith("desktop.dock-")
    ]

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "modules": modules_out,
        "edges": sorted(edges, key=lambda e: (e["from"], e["to"])),
        "audit": {
            "single_point": single_point,
            "isolated": isolated,
            "degraded": soft_missing_all,
            "summary_providers": summary_providers,
            "dock_cards": dock_cards,
            "dock_overload": len(dock_cards) > 6,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="能力依赖图导出（提案 C 数据侧）")
    ap.add_argument("--json", default="", help="落盘路径（默认 stdout）")
    ap.add_argument("--modules-dir", default=str(MODULES_DIR))
    args = ap.parse_args()

    data = build(Path(args.modules_dir))
    out = json.dumps(data, ensure_ascii=False, indent=2)
    if args.json:
        Path(args.json).write_text(out + "\n", encoding="utf-8")
        print(f"已写入 {args.json}")
    else:
        print(out)

    # 摘要
    a = data["audit"]
    print(
        f"\n模块 {len(data['modules'])} · 硬依赖边 "
        f"{sum(1 for e in data['edges'] if e['kind'] == 'hard')} · "
        f"单点 {a['single_point'] or '无'} · 孤岛 {a['isolated'] or '无'} · "
        f"degraded {len(a['degraded'])}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
