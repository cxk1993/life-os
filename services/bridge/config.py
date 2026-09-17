"""桥配置：读取 config.yaml，构造 Lib 列表。

★ PSK 优先级：环境变量 BRIDGE_PSK > config.yaml 的 psk 字段（后者仅供本地开发）。
  生产必须把 BRIDGE_PSK 注入到 nssm 服务的环境里，config.yaml 里留空或写占位。
★ 默认库路径是主人真实路径（见 config.yaml）。本机没有真实 vault 时，自测用临时 config。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Lib:
    id: str
    name: str
    path: str
    mode: str = "ro"  # ro | rw（v0.1 写默认关闭，由 mode 控制）
    enabled: bool = True
    include: list[str] = field(default_factory=lambda: ["**/*.md"])
    exclude: list[str] = field(default_factory=list)

    def abs_path(self) -> Path:
        return Path(self.path).expanduser().resolve()


@dataclass
class BridgeConfig:
    psk: str
    libs: list[Lib]

    def lib(self, lib_id: str) -> Lib | None:
        for lib in self.libs:
            if lib.id == lib_id:
                return lib
        return None

    def enabled_libs(self) -> list[Lib]:
        return [lib for lib in self.libs if lib.enabled]


def load_config(path: str | Path) -> BridgeConfig:
    raw: dict[str, Any] = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    # ★ PSK 只从环境变量走；config.yaml 的 psk 仅本地开发兜底，生产必须置空并设环境变量
    psk = os.environ.get("BRIDGE_PSK") or raw.get("psk", "")
    libs: list[Lib] = []
    for item in raw.get("libs", []):
        libs.append(
            Lib(
                id=item["id"],
                name=item.get("name", item["id"]),
                path=item["path"],
                mode=item.get("mode", "ro"),
                enabled=bool(item.get("enabled", True)),
                include=item.get("include", ["**/*.md"]),
                exclude=item.get("exclude", []),
            )
        )
    return BridgeConfig(psk=psk, libs=libs)
