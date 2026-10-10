"""L2 判据 · MCP 工具 path 全量审计（ISSUE-008 验收判据包本体）。

判据（/ 2026-09-20 口径 26→25：habits.log.write 按
T18「宁可少暴露不可错转发」删除 provides）：
    全部 MCP 工具的推导 path（registry_adapter.py 规则）与各模块真实路由逐一对表，
    差集必须为 0；tools/call 抽测属生产调用级（需 PAT，另行执行）。

规则复刻自 modules/mcp/registry_adapter.py 的 derive_tool（唯一判据载体）：
    tool name = provides.replace('.', '_')
    method    = 末段动词查表（read/list/search/free/get→GET；write/create→POST；update→PUT；delete/remove→DELETE）
    path      = manifest api.tools 显式声明优先，未声明 resource 走机械「resource+s」
                ← ISSUE-008 故障点（机械加 s）与方案 A 修复点
    scope     = 首段:末段
    跳过      = <3 段 ｜ 未知动词 ｜ 插件无 api.base

用法：
    python tools/accept_probe/mcp_path_audit.py            # 对表+判定（path+名集合双闸门）
    python tools/accept_probe/mcp_path_audit.py --verbose   # 附每条工具明细
    python tools/accept_probe/mcp_path_audit.py --base <repo>  # 指定仓库根（负例测试沙栏用，
                                                              #  默认本脚本所在仓库；事故教训）

退出码：0=全对表（修复后应为 0）；1=存在差集（修复前应为 1，列出故障工具）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

MODULES_DIR = Path(__file__).resolve().parents[2] / "services" / "api" / "modules"
ADAPTER = MODULES_DIR / "mcp" / "registry_adapter.py"
EXPECTED_PATH = Path(__file__).resolve().parent / "expected.json"

_METHOD_BY_VERB = {
    "read": "GET", "list": "GET", "search": "GET", "free": "GET", "get": "GET",
    "write": "POST", "create": "POST", "update": "PUT", "delete": "DELETE", "remove": "DELETE",
}
# ★ 多行装饰器兼容：@router.post(\n    "/entries", ...) 是项目既有写法
#（finance/router.py:84），\s* 覆盖「( 后换行缩进再到路径字面量」。
_ROUTE_RE = re.compile(r'@router\.(get|post|put|patch|delete)\(\s*"([^"]+)"')


def load_manifest(module_dir: Path) -> dict:
    return json.loads((module_dir / "manifest.json").read_text(encoding="utf-8"))


def actual_routes(module_dir: Path, api_base: str) -> set[tuple[str, str]]:
    """模块真实路由集 {(METHOD, path)}：router.py 本地路径 + manifest api.base 前缀
    （挂载口径见 core/plugins/discover.py:183 `registry.mount(..., prefix=api.base)`）；
    path 归一：参数段→{}、去尾部斜杠。"""
    base = api_base.rstrip("/")
    out: set[tuple[str, str]] = set()
    for py in module_dir.rglob("*.py"):
        for m in _ROUTE_RE.finditer(py.read_text(encoding="utf-8", errors="ignore")):
            method, path = m.group(1).upper(), m.group(2)
            full = base + path if path.startswith("/") else f"{base}/{path}"
            out.add((method, norm_path(full)))
    return out


def derive(provides: str, api_base: str,
           tool_routes: dict[str, str] | None = None) -> tuple[str, str, str] | None:
    parts = provides.split(".")
    if len(parts) < 3:
        return None
    verb = parts[-1]
    method = _METHOD_BY_VERB.get(verb)
    if method is None:
        return None
    resource = parts[-2]
    name = "_".join(parts)
    # ISSUE-008 方案 A（2026-09-20）：与 registry_adapter.derive_tool 字面同步——
    # manifest api.tools 显式声明优先，未声明 resource 走机械「resource+s」推导。
    # route 值兼容两种形态：相对 router 段（拼 api.base，规范）
    # 与完整路径（已含 api.base，原样采用）。
    explicit = (tool_routes or {}).get(resource)
    base = api_base.rstrip("/")
    if explicit is None:
        path = f"{base}/{resource}s"
    elif explicit.startswith(base):
        path = explicit
    else:
        path = f"{base}{explicit}"
    return name, method, path


def norm_path(p: str) -> str:
    return re.sub(r"\{[^}]+\}", "{}", p).rstrip("/") or "/"


def main() -> int:
    global MODULES_DIR, ADAPTER
    ap = argparse.ArgumentParser(description="MCP 工具 path+名集合双闸门审计（ISSUE-008 判据）")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--base", default=None,
                    help="仓库根（默认本脚本所在仓库）；负例测试请在副本目录上跑，勿碰真文件")
    args = ap.parse_args()

    if args.base:
        MODULES_DIR = Path(args.base).resolve() / "services" / "api" / "modules"
        ADAPTER = MODULES_DIR / "mcp" / "registry_adapter.py"
    if not ADAPTER.exists():
        print(f"找不到 {ADAPTER}（判据源失效，先查仓库结构）")
        return 2

    tools: list[dict] = []
    for mdir in sorted(MODULES_DIR.iterdir()):
        mf = mdir / "manifest.json"
        if not mf.exists():
            continue
        m = load_manifest(mdir)
        api = (m.get("api") or {}).get("base", "")
        if not api:
            continue
        tool_routes = (m.get("api") or {}).get("tools") or {}
        routes = actual_routes(mdir, api)
        for cap in m.get("provides") or []:
            d = derive(cap, api, tool_routes)
            if d is None:
                continue
            name, method, path = d
            hit = (method, norm_path(path)) in routes
            tools.append({
                "tool": name, "provides": cap, "method": method,
                "derived_path": path, "route_hit": hit, "plugin": m.get("id"),
            })

    tools.sort(key=lambda t: t["tool"])
    bad = [t for t in tools if not t["route_hit"]]
    print(f"MCP path 审计：工具 {len(tools)} 个，对表失败 {len(bad)} 个")
    for t in (tools if args.verbose else bad):
        mark = "✅" if t["route_hit"] else "❌"
        print(f"  {mark} {t['tool']:<28} {t['method']:<6} {t['derived_path']}"
              + ("" if t["route_hit"] else "   ← 真实路由无此 method+path"))

    # ── 名集合契约对表（头号：名级 tools/list 对表闸门）──
    # 期望名清单（expected.json mcp_tools.names，人审写死）vs 代码派生名集合：
    # 缺=有人删了 provides/声明；多=有人加了工具——都要红，逼一次契约回帖（禁静默增删）。
    name_bad: list[str] = []
    exp_cfg = {}
    try:
        exp_cfg = json.loads(EXPECTED_PATH.read_text(encoding="utf-8")).get("suites", {}).get("mcp_tools", {})
    except Exception:
        pass
    if exp_cfg.get("enabled"):
        expected_names = set(exp_cfg.get("names") or [])
        derived_names = {t["tool"] for t in tools}
        missing = sorted(expected_names - derived_names)
        extra = sorted(derived_names - expected_names)
        count_ok = len(tools) == exp_cfg.get("count")
        print(f"\n名集合契约对表：期望 {exp_cfg.get('count')} / 派生 {len(tools)}"
              f"｜缺 {len(missing)}：{missing or '无'}｜多 {len(extra)}：{extra or '无'}"
              f"｜计数{'✅' if count_ok else '❌'}")
        if missing or extra or not count_ok:
            name_bad = missing + extra + ([] if count_ok else ["<count>"])

    if bad or name_bad:
        print("\n闸门 RED ❌（path 差集或名集合契约未过；修复/契约回帖后应全绿 exit 0）")
        return 1
    print(f"\nALL_PATHS_MATCH ✅（{len(tools)} 工具推导 path 与真实路由全对表）")
    print("NAMES_CONTRACT_MATCH ✅（派生名集合与 expected.json 契约一致）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
