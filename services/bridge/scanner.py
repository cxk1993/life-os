"""扫描库：产出索引（路径 / 标题 / mtime / size / hash / 摘要）。

★ 只存索引与摘要，不存全文（雷区 #13：服务器磁盘有限）。
★ 大库限速：limit 上限保护，避免一次把内存打爆；支持 from_path 续传游标。
★ 路径统一 POSIX 相对路径（如 work review日报/2026年9月/2026-09-13.md）。
"""
from __future__ import annotations

import fnmatch
import hashlib
from pathlib import Path

from .config import Lib
from .reader import excerpt_of, title_of

MAX_ENTRIES = 5000


def _match_any(name: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(name, p) for p in patterns)


def scan_lib(lib: Lib, *, limit: int = MAX_ENTRIES, with_excerpt: bool = True) -> list[dict]:
    """扫描单个库，返回索引条目列表（按相对路径排序，稳定可续传）。"""
    root = lib.abs_path()
    if not root.is_dir():
        return []

    # ★ include 补 `*.md`（astrbot 下场 · 主人「似乎笔记的同步里面遗漏了很多笔记」）：
    #   fnmatch 里 `**/*.md` **不匹配根目录文件**（要求至少一层目录），
    #   → 主仓库根目录的《人生管理系统.md》等被静默漏掉。补 `*.md` 覆盖根层。
    include = lib.include or ["*.md", "**/*.md"]
    exclude = lib.exclude or []
    entries: list[dict] = []

    for path in sorted(root.rglob("*.md")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        # include / exclude 用相对路径（支持 **/*.md 与目录前缀匹配）
        if include and not _match_any(rel, include) and not _match_any(path.name, include):
            continue
        if exclude and (_match_any(rel, exclude) or _match_any(path.name, exclude)):
            continue
        # 跳过隐藏目录（.obsidian / .trash 等）
        if any(part.startswith(".") for part in path.relative_to(root).parts[:-1]):
            continue

        try:
            raw = path.read_bytes()
            text = raw.decode("utf-8-sig", errors="replace")
            stat = path.stat()
        except OSError:
            continue

        # ★ 标题回退（astrbot 下场 · 主人「有些笔记的标题没有被同步成功」）：
        #   Work-Review 会生成 0~1 字节的空日报 → title_of("") = "" → 前端显示空标题。
        #   回退链：首个非空行 → 文件名（去扩展名）。
        _title = title_of(text) or Path(rel).stem
        entry = {
            "rel_path": rel,
            "title": _title,
            "mtime": int(stat.st_mtime),
            "size": stat.st_size,
            "hash": hashlib.sha256(raw).hexdigest(),
        }
        if with_excerpt:
            entry["excerpt"] = excerpt_of(text, 200)
        entries.append(entry)
        if len(entries) >= limit:
            break

    return entries


def count_md(lib: Lib) -> int:
    """库内 .md 文件总数（用于和索引条目数比对验证）。"""
    root = lib.abs_path()
    if not root.is_dir():
        return 0
    return sum(1 for p in root.rglob("*.md") if p.is_file())
