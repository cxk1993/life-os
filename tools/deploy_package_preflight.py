#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""· 部署包完整性预检（M1 纯本地比对）。

只读比对「变更文件清单」与「path→MD5 表」，输出缺口/不一致报告。
不修改任何文件、不访问网络、不碰生产。

用法：
  python tools/deploy_package_preflight.py --files files.txt --hashes hashes.json --base .
  python tools/deploy_package_preflight.py --files files.json --hashes hashes.json
  python tools/deploy_package_preflight.py --self-test
  python tools/deploy_package_preflight.py --help

退出码：
  0 = 全绿（清单内文件均存在且 MD5 一致）
  1 = 存在缺失文件（可能同时有 MD5 不符，两类都会打印）
  2 = 无缺失，但存在 MD5 不符
  3 = 用法/输入错误
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from pathlib import Path

__version__ = "0.1.0-m1"
CHUNK = 1024 * 1024


def md5_file(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        while True:
            block = f.read(CHUNK)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def load_file_list(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
        if isinstance(data, dict) and "files" in data:
            data = data["files"]
        if not isinstance(data, list):
            raise ValueError("files json must be a list or {files:[]}")
        return [str(x).strip().replace("\\", "/") for x in data if str(x).strip()]
    lines: list[str] = []
    for raw in text.splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        lines.append(s.replace("\\", "/"))
    return lines


def load_hashes(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(data, list):
        out: dict[str, str] = {}
        for item in data:
            if not isinstance(item, dict):
                raise ValueError("hashes list items must be objects")
            p = item.get("path") or item.get("file")
            m = item.get("md5") or item.get("hash")
            if not p or not m:
                raise ValueError("hashes list items need path+md5")
            out[str(p).replace("\\", "/")] = str(m).lower()
        return out
    if not isinstance(data, dict):
        raise ValueError("hashes must be object or list")
    # allow nested {"hashes": {...}}
    if "hashes" in data and isinstance(data["hashes"], dict):
        data = data["hashes"]
    return {str(k).replace("\\", "/"): str(v).lower() for k, v in data.items()}


def preflight(
    base: Path,
    files: list[str],
    hashes: dict[str, str],
) -> tuple[int, list[str], list[str], list[str]]:
    """Return (exit_code, missing, mismatch, ok_paths)."""
    missing: list[str] = []
    mismatch: list[str] = []
    ok: list[str] = []
    for rel in files:
        rel_n = rel.replace("\\", "/").lstrip("./")
        expected = hashes.get(rel_n)
        if expected is None:
            # try suffix match if list used shorter prefix
            for k, v in hashes.items():
                if k.endswith(rel_n) or rel_n.endswith(k):
                    expected = v
                    rel_n = k
                    break
        target = base / rel_n
        if not target.is_file():
            missing.append(rel_n)
            continue
        actual = md5_file(target)
        if expected is None:
            mismatch.append(f"{rel_n}  (no expected md5 in table; actual={actual})")
            continue
        if actual != expected:
            mismatch.append(f"{rel_n}  expected={expected} actual={actual}")
        else:
            ok.append(rel_n)
    if missing:
        code = 1
    elif mismatch:
        code = 2
    else:
        code = 0
    return code, missing, mismatch, ok


def render_report(
    base: Path,
    files: list[str],
    code: int,
    missing: list[str],
    mismatch: list[str],
    ok: list[str],
) -> str:
    lines = [
        "deploy package preflight (M1 local)",
        f"base={base}",
        f"listed={len(files)} ok={len(ok)} missing={len(missing)} md5_mismatch={len(mismatch)}",
        f"exit={code}  (0=green 1=missing 2=md5_mismatch)",
        "",
    ]
    if missing:
        lines.append("## MISSING")
        lines.extend(f"  - {p}" for p in missing)
        lines.append("")
    if mismatch:
        lines.append("## MD5_MISMATCH")
        lines.extend(f"  - {p}" for p in mismatch)
        lines.append("")
    if code == 0:
        lines.append("## ALL_GREEN")
        lines.append(f"  {len(ok)}/{len(files)} files match hash table")
    return "\n".join(lines) + "\n"


def _self_test() -> int:
    """Issue-006 style replay in a temp dir (uuid4 names, no third-party)."""
    tmp = Path.cwd() / f".tx_tool01_selftest_{uuid.uuid4().hex}"
    tmp.mkdir(parents=True, exist_ok=False)
    try:
        # Minimal stand-in for ISSUE-006 shape: 3 files with known md5
        samples = {
            "services/api/core/app.py": b"print('app')\n",
            "services/api/modules/agents/migrations/0001_init.py": b"# agents\n",
            "services/api/modules/todo/migrations/0001_init.py": b"# todo\n",
        }
        hashes: dict[str, str] = {}
        for rel, content in samples.items():
            p = tmp / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(content)
            hashes[rel] = hashlib.md5(content).hexdigest()

        files = list(samples.keys())
        # 1) all green
        code, missing, mismatch, ok = preflight(tmp, files, hashes)
        assert code == 0 and len(ok) == 3 and not missing and not mismatch, (code, missing, mismatch)

        # 2) missing file
        code2, missing2, _, _ = preflight(tmp, files + ["services/api/modules/ghost.py"], hashes)
        assert code2 == 1 and "ghost.py" in missing2[0], (code2, missing2)

        # 3) md5 mismatch
        bad = dict(hashes)
        bad["services/api/core/app.py"] = "0" * 32
        code3, missing3, mismatch3, _ = preflight(tmp, files, bad)
        assert code3 == 2 and not missing3 and mismatch3, (code3, missing3, mismatch3)

        # 4) report renders
        rep = render_report(tmp, files, code3, missing3, mismatch3, [])
        assert "MD5_MISMATCH" in rep

        print("SELF_TEST PASS")
        print(f"  tmp={tmp.name}")
        print("  cases: all_green / missing / md5_mismatch OK")
        return 0
    finally:
        # best-effort cleanup
        try:
            for p in sorted(tmp.rglob("*"), reverse=True):
                if p.is_file():
                    p.unlink()
                elif p.is_dir():
                    p.rmdir()
            tmp.rmdir()
        except OSError:
            print(f"  warn: cleanup incomplete: {tmp}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="deploy_package_preflight",
        description="M1: local deploy package preflight (read-only).",
    )
    ap.add_argument("--files", help="change file list (.txt one path/line or .json array)")
    ap.add_argument("--hashes", help="path->md5 json table")
    ap.add_argument("--base", default=".", help="local root (default: .)")
    ap.add_argument("--self-test", action="store_true", help="run built-in acceptance cases")
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = ap.parse_args(argv)

    if args.self_test:
        return _self_test()

    if not args.files or not args.hashes:
        ap.print_usage(sys.stderr)
        print("error: --files and --hashes are required (or use --self-test)", file=sys.stderr)
        return 3

    base = Path(args.base).resolve()
    try:
        files = load_file_list(Path(args.files))
        hashes = load_hashes(Path(args.hashes))
    except (OSError, ValueError, json.JSONDecodeError) as e:
        print(f"error: bad input: {e}", file=sys.stderr)
        return 3

    if not files:
        print("error: empty file list", file=sys.stderr)
        return 3

    code, missing, mismatch, ok = preflight(base, files, hashes)
    sys.stdout.write(render_report(base, files, code, missing, mismatch, ok))
    return code


if __name__ == "__main__":
    sys.exit(main())
