"""文件监听：watchdog 增量推送；watchdog 不可用时回退到轮询。

★ 验收项「新建一个 .md → 30 秒内索引里出现」由本模块保证。
★ 无论是 watchdog 还是轮询，事件都转成统一的增量条目（rel_path / mtime / size / hash / kind），
  交给上层推给服务器（v0.1 服务器侧是拉模式 + 本机推送并存）。
★ 不依赖新增第三方依赖：优先 watchdog，缺失则轮询（间隔 3s，远小于 30s 要求）。
"""
from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path

from .config import Lib
from .reader import title_of

log = logging.getLogger("bridge.watcher")

POLL_INTERVAL_S = 3


def _entry_for(lib: Lib, path: Path, kind: str) -> dict | None:
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8-sig", errors="replace")
        stat = path.stat()
    except OSError:
        return None
    return {
        "rel_path": path.relative_to(lib.abs_path()).as_posix(),
        "title": title_of(text),
        "mtime": int(stat.st_mtime),
        "size": stat.st_size,
        "hash": hashlib.sha256(raw).hexdigest(),
        "kind": kind,  # created | modified | deleted
    }


def start_watchdog(lib: Lib, on_change) -> object | None:
    """启动 watchdog 监听；失败返回 None（调用方回退轮询）。"""
    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except ImportError:
        return None

    root = lib.abs_path()
    if not root.is_dir():
        return None

    class _Handler(FileSystemEventHandler):
        def on_created(self, event):
            if not event.is_directory and str(event.src_path).endswith(".md"):
                e = _entry_for(lib, Path(event.src_path), "created")
                if e:
                    on_change(e)

        def on_modified(self, event):
            if not event.is_directory and str(event.src_path).endswith(".md"):
                e = _entry_for(lib, Path(event.src_path), "modified")
                if e:
                    on_change(e)

        def on_deleted(self, event):
            if not event.is_directory and str(event.src_path).endswith(".md"):
                rel = Path(event.src_path).relative_to(root).as_posix()
                on_change({"rel_path": rel, "kind": "deleted"})

    observer = Observer()
    observer.schedule(_Handler(), str(root), recursive=True)
    observer.daemon = True
    observer.start()
    log.info("watchdog 已启动", extra={"lib": lib.id})
    return observer


def start_poll(lib: Lib, on_change) -> dict:
    """轮询回退：每 3s 扫一次 mtime/hash，变化即推送。"""
    root = lib.abs_path()
    if not root.is_dir():
        return {"stop": lambda: None}

    state: dict[str, tuple[int, str]] = {}

    def _snapshot() -> None:
        for path in root.rglob("*.md"):
            if not path.is_file():
                continue
            if any(part.startswith(".") for part in path.relative_to(root).parts[:-1]):
                continue
            try:
                raw = path.read_bytes()
                st = path.stat()
            except OSError:
                continue
            rel = path.relative_to(root).as_posix()
            h = hashlib.sha256(raw).hexdigest()
            prev = state.get(rel)
            if prev is None:
                e = _entry_for(lib, path, "created")
                if e:
                    on_change(e)
            elif prev != (int(st.st_mtime), h):
                e = _entry_for(lib, path, "modified")
                if e:
                    on_change(e)
            state[rel] = (int(st.st_mtime), h)
        # 清理已删除
        for rel in list(state):
            if not (root / rel).exists():
                state.pop(rel, None)
                on_change({"rel_path": rel, "kind": "deleted"})

    def _loop() -> None:
        # 首轮建立基线，不再逐条推送 created（避免启动时刷屏）
        for path in root.rglob("*.md"):
            if path.is_file():
                try:
                    state[path.relative_to(root).as_posix()] = (
                        int(path.stat().st_mtime),
                        hashlib.sha256(path.read_bytes()).hexdigest(),
                    )
                except OSError:
                    continue
        while True:
            time.sleep(POLL_INTERVAL_S)
            try:
                _snapshot()
            except Exception as exc:  # noqa: BLE001
                log.warning("轮询异常", extra={"lib": lib.id, "exc": str(exc)})

    import threading

    t = threading.Thread(target=_loop, daemon=True)
    t.start()
    log.info("轮询监听已启动（watchdog 不可用）", extra={"lib": lib.id})
    return {"stop": lambda: None}


def start_watcher(lib: Lib, on_change) -> object:
    """统一入口：优先 watchdog，回退轮询。返回可被停止的句柄。"""
    obs = start_watchdog(lib, on_change)
    if obs is not None:
        return obs
    return start_poll(lib, on_change)
