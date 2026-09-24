"""B 案防退化：manifest.entry 格式契约测试。"""
from __future__ import annotations

import json
import re
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
ENTRY_RE = re.compile(r"^@/apps/[a-z][a-z0-9-]*$")


def _iter_manifests():
    for p in sorted((API_ROOT / "modules").glob("*/manifest.json")):
        yield p, json.loads(p.read_text(encoding="utf-8"))


def test_entry_format_at_apps_slash() -> None:
    """entry 必须是 @/apps/<id> 或空；禁止 @apps/（少一斜杠，slot 生态曾全灭）。"""
    for p, m in _iter_manifests():
        e = (m.get("entry") or "").strip()
        if not e:
            continue
        # 仅校验前端入口形态；api.tools 里的 /entries 不在本字段
        assert ENTRY_RE.match(e), f"{p}: entry={e!r} 须匹配 @/apps/<id>"
        assert not e.startswith("@apps/"), f"{p}: 禁止 @apps/ 形态"
        # id 与目录一致（目录名可含横线）
        assert e == f"@/apps/{m['id']}", f"{p}: entry 与 manifest.id 不一致"


def test_entry_id_matches_directory() -> None:
    for p, m in _iter_manifests():
        assert m["id"] == p.parent.name, f"{p}: id={m['id']} != dir {p.parent.name}"
