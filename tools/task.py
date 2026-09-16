#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Life-OS 跨平台任务入口（项目唯一入口的真实实现）。

为什么不是纯 Makefile？
    总纲 §4 雷区 #1/#2 说得清楚：不许假设目标机器有 make / grep / find / wmic。
    主人这台 Win11 没有 make。所以真正的实现放在这个跨平台脚本里，
    根目录的 Makefile 只是它的薄壳 —— 两条入口行为完全一致。

用法（在项目根目录执行）：
    python tools/task.py help
    python tools/task.py setup        # 首次：建 venv + 装前后端依赖
    python tools/task.py dev          # 同起前端 5173 与后端 8000
    python tools/task.py lint         # tsc + eslint + prettier / ruff + mypy
    python tools/task.py test         # vitest + pytest
    python tools/task.py verify       # lint + test + 前端构建（交付前必跑）
    python tools/task.py build        # 前端产物（有 docker 时顺带建镜像）
    python tools/task.py clean        # 清缓存，data/ 绝不动
    python tools/task.py new-plugin --id calendar --name "日程表"

环境变量：
    LIFEOS_PYTHON    指定用于建 venv 的 Python 3.11 可执行文件
    PIP_INDEX_URL    pip 源（国内建议 https://pypi.tuna.tsinghua.edu.cn/simple）
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

if sys.version_info < (3, 11):  # tomllib 需要 3.11+
    print("tools/task.py 需要 Python 3.11+（用于读取 pyproject.toml）", file=sys.stderr)
    raise SystemExit(1)

import tomllib  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "apps" / "web"
API = ROOT / "services" / "api"
VENV = API / ".venv"

WEB_PORT = 5173
API_PORT = 8000
IS_WIN = os.name == "nt"


# ────────────────────────────── 基础设施 ──────────────────────────────
def log(msg: str) -> None:
    print(f"[task] {msg}", flush=True)


def die(msg: str, code: int = 1) -> None:
    print(f"[task] 失败：{msg}", file=sys.stderr, flush=True)
    raise SystemExit(code)


def run(
    cmd: list[str],
    cwd: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    shown = " ".join(cmd)
    log(f"$ {shown}")
    p = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and p.returncode != 0:
        die(f"命令退出码 {p.returncode}：{shown}")
    return p


def find_python311() -> list[str]:
    """找一个 Python 3.11。总纲 §1.1 把后端锁在 3.11，所以这里严格校验。"""
    cands: list[list[str]] = []
    forced = os.environ.get("LIFEOS_PYTHON")
    if forced:
        cands.append([forced])
    cands += [["py", "-3.11"], ["python3.11"], ["python3"], ["python"], [sys.executable]]

    probe = "import sys;print('%d.%d' % sys.version_info[:2])"
    tried: list[str] = []
    for c in cands:
        exe = c[0]
        if not (Path(exe).exists() or shutil.which(exe)):
            continue
        try:
            p = subprocess.run(
                [*c, "-c", probe], capture_output=True, text=True, timeout=30
            )
        except Exception:  # noqa: BLE001
            continue
        out = (p.stdout or "").strip()
        tried.append(f"{' '.join(c):<28} -> {out or (p.stderr or '').strip()[:50]}")
        if p.returncode == 0 and out == "3.11":
            return c
    die(
        "找不到 Python 3.11（总纲 §1.1 锁定 3.11）。已尝试：\n    "
        + "\n    ".join(tried)
        + "\n  解决：设环境变量 LIFEOS_PYTHON 指向 3.11 的可执行文件。"
    )
    return []  # 不会走到


def venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if IS_WIN else "bin/python")


def npm_cmd(args: list[str]) -> list[str]:
    """Windows 上 npm 是 .cmd 批处理，必须经 cmd /c 才能被 subprocess 拉起。"""
    if IS_WIN:
        return ["cmd", "/c", "npm", *args]
    return [shutil.which("npm") or "npm", *args]


def docker_available() -> bool:
    return shutil.which("docker") is not None


# ────────────────────────────── 依赖准备 ──────────────────────────────
def api_dependencies() -> list[str]:
    """从 pyproject.toml 读依赖 —— 单一事实来源，不另建 requirements.txt。"""
    with (API / "pyproject.toml").open("rb") as f:
        data = tomllib.load(f)
    proj = data.get("project", {})
    deps: list[str] = list(proj.get("dependencies", []))
    deps += list(proj.get("optional-dependencies", {}).get("dev", []))
    return deps


def ensure_node() -> None:
    if not shutil.which("node"):
        die("找不到 node。请安装 Node 20+ 并加入 PATH（版本见 .nvmrc）。")


def ensure_venv() -> None:
    if venv_python().exists():
        return
    log("创建后端虚拟环境 services/api/.venv ...")
    run([*find_python311(), "-m", "venv", str(VENV)])


def ensure_api_deps() -> None:
    ensure_venv()
    py = str(venv_python())
    probe = subprocess.run([py, "-c", "import fastapi, sqlmodel"], capture_output=True)
    if probe.returncode == 0:
        return
    log("安装后端依赖（首次会慢一些）...")
    run([py, "-m", "pip", "install", "--upgrade", "pip", "-q"])
    run([py, "-m", "pip", "install", *api_dependencies()])


def ensure_web_deps() -> None:
    ensure_node()
    if (WEB / "node_modules").is_dir():
        return
    log("安装前端依赖（首次会慢一些）...")
    run(npm_cmd(["install"]), cwd=WEB)


def ensure_all() -> None:
    ensure_api_deps()
    ensure_web_deps()


def api_lint_targets() -> list[str]:
    """算出 mypy 该检查哪些路径。

    注意：不能只看"目录存不存在" —— 目录可能只有 .gitkeep 占位
    （core/ db/ modules/ 在对应任务块交付前就是这种状态）。
    一个目录里**一个 .py 都没有**时，mypy 会直接报错退出，
    所以这里必须按"有没有 Python 文件"来判断。
    """
    targets: list[str] = []
    for d in ("core", "db", "modules", "scripts"):
        p = API / d
        if p.is_dir() and any(p.rglob("*.py")):
            targets.append(d)
    for f in ("main.py",):
        if (API / f).exists():
            targets.append(f)
    return targets


# ────────────────────────────── 各条命令 ──────────────────────────────
def cmd_setup(_: argparse.Namespace) -> None:
    ensure_all()
    log("环境就绪。下一步： python tools/task.py dev")


def _pump(name: str, proc: subprocess.Popen[str]) -> None:
    assert proc.stdout is not None
    for line in iter(proc.stdout.readline, ""):
        if not line:
            break
        print(f"[{name}] {line.rstrip()}", flush=True)


def cmd_dev(_: argparse.Namespace) -> None:
    ensure_all()
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    specs = [
        ("web", npm_cmd(["run", "dev"]), WEB),
        (
            "api",
            [str(venv_python()), "-m", "uvicorn", "main:app", "--reload", "--port", str(API_PORT)],
            API,
        ),
    ]
    procs: list[tuple[str, subprocess.Popen[str]]] = []
    for name, cmd, cwd in specs:
        log(f"启动 {name}: {' '.join(cmd)}")
        procs.append(
            (
                name,
                subprocess.Popen(  # noqa: S603
                    cmd,
                    cwd=str(cwd),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    env=env,
                ),
            )
        )

    for name, proc in procs:
        threading.Thread(target=_pump, args=(name, proc), daemon=True).start()

    log(f"前端 http://localhost:{WEB_PORT}    后端 http://localhost:{API_PORT}/docs")
    log("按 Ctrl+C 一起停止。")
    try:
        while any(p.poll() is None for _, p in procs):
            time.sleep(0.5)
        log("有一个服务退出了，一起停。")
    except KeyboardInterrupt:
        log("收到 Ctrl+C，正在停止 ...")
    finally:
        for _, p in procs:
            if p.poll() is None:
                p.terminate()
        for _, p in procs:
            try:
                p.wait(timeout=10)
            except Exception:  # noqa: BLE001
                p.kill()


def cmd_lint(_: argparse.Namespace) -> None:
    ensure_all()

    log("── 前端静态检查 ──")
    for script in ("typecheck", "lint", "format:check"):
        run(npm_cmd(["run", script]), cwd=WEB)

    log("── 后端静态检查 ──")
    py = str(venv_python())
    run([py, "-m", "ruff", "check", "."], cwd=API)
    targets = api_lint_targets()
    if targets:
        run([py, "-m", "mypy", *targets], cwd=API)
    else:
        log("跳过 mypy：core/ db/ modules/ main.py 都还不存在。")

    purity = API / "scripts" / "check_kernel_purity.py"
    if purity.exists():
        run([py, str(purity)], cwd=API)
    else:
        log("跳过内核洁癖检查：scripts/check_kernel_purity.py 未就位（T14 交付后自动启用）。")

    log("lint 通过。")


def cmd_test(_: argparse.Namespace) -> None:
    ensure_all()
    run(npm_cmd(["run", "test"]), cwd=WEB)
    run([str(venv_python()), "-m", "pytest"], cwd=API)
    log("test 通过。")


def cmd_verify(_: argparse.Namespace) -> None:
    cmd_lint( argparse.Namespace() )
    cmd_test( argparse.Namespace() )
    log("── 前端构建 ──")
    run(npm_cmd(["run", "build"]), cwd=WEB)
    log("verify 通过：lint + test + build 全绿。")


def cmd_build(_: argparse.Namespace) -> None:
    ensure_web_deps()
    log("── 前端产物 ──")
    run(npm_cmd(["run", "build"]), cwd=WEB)

    log("── 后端镜像 ──")
    compose = ROOT / "docker-compose.yml"
    if not docker_available():
        log("本机没有 docker，跳过镜像构建。")
        log("说明：镜像与生产编排由 T13 负责；本机开发用 `python tools/task.py dev` 即可。")
    elif not compose.exists():
        log("找不到 docker-compose.yml，跳过。")
    else:
        run(["docker", "compose", "-f", str(compose), "build"])


def cmd_clean(_: argparse.Namespace) -> None:
    targets = [
        WEB / "dist",
        WEB / "node_modules" / ".vite",
        API / ".pytest_cache",
        API / ".mypy_cache",
        API / ".ruff_cache",
    ]
    for t in targets:
        if t.exists():
            log(f"删除 {t.relative_to(ROOT)}")
            shutil.rmtree(t, ignore_errors=True)

    removed = 0
    for p in API.rglob("__pycache__"):
        if VENV in p.parents:
            continue
        shutil.rmtree(p, ignore_errors=True)
        removed += 1
    log(f"清理 __pycache__ {removed} 个。")
    log("data/ 未动。clean 完成。")


def cmd_new_plugin(args: argparse.Namespace) -> None:
    script = API / "scripts" / "create_plugin.py"
    if not script.exists():
        die(
            "services/api/scripts/create_plugin.py 还不存在 —— 它是 T14（插件框架）的交付物。\n"
            "  T14 交付后本命令自动可用。"
        )
    # ★ 必须转发 --kind：create_plugin.py 的默认是 third-party
    #   （落 `plugins/<id>/`，带 api/ 子目录），而内置业务插件要的是 builtin
    #   （落 `services/api/modules/<id>/` + `apps/web/src/apps/<id>/`）。
    #   早期版本漏了这个参数，于是内置卡的骨架全被生成成第三方布局：
    #   多出 api/ 层、迁移落错位置、web 入口根本没生成。
    run([str(venv_python()), str(script), args.id, args.name, "--kind", args.kind], cwd=API)


def cmd_help(_: argparse.Namespace) -> None:
    print(
        """
Life-OS 任务入口（与 Makefile 等价）

  setup        首次准备：建 venv + 装前后端依赖
  dev          同起前端 5173 与后端 8000（Ctrl+C 一起停）
  lint         前端 tsc + eslint + prettier ／ 后端 ruff + mypy
  test         前端 vitest ／ 后端 pytest
  verify       交付前必跑：lint + test + 前端构建
  build        前端产物（有 docker 时顺带建后端镜像）
  clean        清构建缓存（data/ 绝不动）
  new-plugin   生成新插件骨架（脚手架由 T14 提供）
  help         显示这段说明
""".strip()
    )


def main() -> None:
    parser = argparse.ArgumentParser(prog="task", description="Life-OS 跨平台任务入口")
    sub = parser.add_subparsers(dest="command")

    for name, fn, help_text in [
        ("help", cmd_help, "显示帮助"),
        ("setup", cmd_setup, "首次准备依赖"),
        ("dev", cmd_dev, "同时启动前后端"),
        ("lint", cmd_lint, "静态检查"),
        ("test", cmd_test, "跑测试"),
        ("verify", cmd_verify, "lint + test + build"),
        ("build", cmd_build, "构建产物"),
        ("clean", cmd_clean, "清缓存"),
    ]:
        p = sub.add_parser(name, help=help_text)
        p.set_defaults(func=fn)

    p_np = sub.add_parser("new-plugin", help="生成新插件骨架")
    p_np.add_argument("--id", required=True, help="插件 id（小写英文，等于目录名）")
    p_np.add_argument("--name", required=True, help="插件中文名")
    p_np.add_argument(
        "--kind",
        choices=["builtin", "third-party"],
        default="builtin",
        help="插件类型，默认 builtin（内置插件的骨架分落两处）",
    )
    p_np.set_defaults(func=cmd_new_plugin)

    args = parser.parse_args()
    if not getattr(args, "func", None):
        cmd_help(args)
        return
    args.func(args)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
