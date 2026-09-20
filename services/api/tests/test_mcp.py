"""T18 MCP Server 测试。

覆盖：
  - derive_tool 机械映射（表驱动：名称/方法/路径/scope/未知动词跳过）
  - PAT 生命周期：创建（明文只回一次）→ 列表无明文 → patch scopes → 吊销 → 401
  - MCP 端点鉴权：无头 / 非 PAT 前缀 / 假 token → 401 problem+json
  - 协议三原语：initialize / tools/list / tools/call（越权 403 + 拒绝审计）
  - notifications → 202；未知 method → -32601
  - ★ 模块洁癖自检：modules/mcp/ 源码零业务词、零业务插件 import

数据库隔离：临时库 ./data/tmp_t18mcp.db。tools/list 只读磁盘 manifest + 库，
转发在测试里用 monkeypatch 替换（真实转发链路由 verify_t18_criterion.py 守门）。
"""
from __future__ import annotations

import os

# ★ 必须在 import 任何内核/模块之前设置临时库，init_engine 只认一次。
os.environ["DB_PATH"] = "./data/tmp_t18mcp.db"

import ast  # noqa: E402  （模块级：_is_docstring 也要用）
import hashlib  # noqa: E402
import json  # noqa: E402
from pathlib import Path  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import SQLModel  # noqa: E402

from core.app import create_app  # noqa: E402
from core.security import create_access_token  # noqa: E402
from db.engine import get_engine, init_engine  # noqa: E402
from modules.mcp import mcp_server  # noqa: E402
from modules.mcp.auth import PAT_PREFIX  # noqa: E402
from modules.mcp.registry_adapter import derive_tool  # noqa: E402

AUTH = {"Authorization": f"Bearer {create_access_token('admin')}"}


@pytest.fixture(scope="module")
def client():
    init_engine()
    engine = get_engine()
    # 建全部已注册表（mcp_pat + 内核表）；checkfirst 幂等。
    SQLModel.metadata.create_all(engine)
    app = create_app()
    c = TestClient(app)
    yield c
    engine.dispose()


@pytest.fixture()
def pat(client):
    """建一个带 calendar:read/write 的 PAT，返回 (明文, 头, id)。"""
    r = client.post(
        "/api/v1/mcp/pats",
        json={"name": "测试-PAT", "scopes": ["calendar:read", "calendar:write"]},
        headers=AUTH,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    plain = body["token"]
    return plain, {"Authorization": f"Bearer {plain}"}, body["id"]


def _rpc(method: str, params: dict | None = None, msg_id: int | str = 1) -> dict:
    msg: dict = {"jsonrpc": "2.0", "id": msg_id, "method": method}
    if params is not None:
        msg["params"] = params
    return msg


# ───────────────────────── 机械映射（纯函数，表驱动） ─────────────────────────
@pytest.mark.parametrize(
    ("provides", "base", "expect"),
    [
        ("calendar.event.write", "/api/v1/calendar",
         ("calendar_event_write", "POST", "/api/v1/calendar/events", "calendar:write")),
        ("calendar.slot.free", "/api/v1/calendar",
         ("calendar_slot_free", "GET", "/api/v1/calendar/slots", "calendar:free")),
        ("notes.note.read", "/api/v1/notes",
         ("notes_note_read", "GET", "/api/v1/notes/notes", "notes:read")),
        ("finance.snapshot.read", "/api/v1/finance",
         ("finance_snapshot_read", "GET", "/api/v1/finance/snapshots", "finance:read")),
        ("todo.item.update", "/api/v1/todo",
         ("todo_item_update", "PUT", "/api/v1/todo/items", "todo:update")),
        ("diary.entry.delete", "/api/v1/diary",
         ("diary_entry_delete", "DELETE", "/api/v1/diary/entrys", "diary:delete")),
    ],
)
def test_derive_tool_mechanical(provides, base, expect):
    t = derive_tool(provides, base, "someplugin")
    assert t is not None
    assert (t.name, t.method, t.path, t.scope) == expect


@pytest.mark.parametrize("bad", ["only.two", "a.b.unknownverb", ""])
def test_derive_tool_skips_invalid(bad):
    assert derive_tool(bad, "/api/v1/x", "p") is None


# ─────────────────── 路径例外表（ISSUE-008） ───────────────────
@pytest.mark.parametrize(
    ("provides", "base", "plugin_id", "expect_path"),
    [
        # 实证故障 1：dashboard.today.read 真实路由是 /today（非机械推导的 /todays）
        ("dashboard.today.read", "/api/v1/dashboard", "dashboard", "/api/v1/dashboard/today"),
        # 实证故障 2：dashboard.system-health.read 真实路由是 /health-of-system
        ("dashboard.system-health.read", "/api/v1/dashboard", "dashboard",
         "/api/v1/dashboard/health-of-system"),
        # 防误伤：例外表按 plugin_id 限定，别的插件的 todays 仍走机械推导
        ("other.today.read", "/api/v1/other", "other", "/api/v1/other/todays"),
    ],
)
def test_derive_tool_path_overrides(provides, base, plugin_id, expect_path):
    t = derive_tool(provides, base, plugin_id)
    assert t is not None
    assert t.path == expect_path


# ───────────────────────── PAT 生命周期 ─────────────────────────
def test_pat_create_returns_plaintext_once(client):
    r = client.post(
        "/api/v1/mcp/pats", json={"name": "一次性", "scopes": ["calendar:read"]},
        headers=AUTH,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["token"].startswith(PAT_PREFIX)
    # 列表里绝无明文
    r2 = client.get("/api/v1/mcp/pats", headers=AUTH)
    names_and_prefixes = json.dumps(r2.json(), ensure_ascii=False)
    assert body["token"] not in names_and_prefixes
    assert body["token_prefix"] in names_and_prefixes
    # 库里也绝无明文（SELECT 证明无明文列）
    from db.engine import get_engine as ge

    engine = ge()
    with engine.connect() as conn:
        rows = conn.exec_driver_sql(
            "SELECT name FROM pragma_table_info('mcp_pat')"
        ).fetchall()
    cols = {row[0] for row in rows}
    assert "token_hash" in cols and "token_prefix" in cols
    assert "token" not in cols and "plaintext" not in cols
    # 哈希对得上、明文对不上
    with engine.connect() as conn:
        hashes = conn.exec_driver_sql("SELECT token_hash FROM mcp_pat").fetchall()
    assert hashlib.sha256(body["token"].encode()).hexdigest() in {h[0] for h in hashes}


def test_pat_revoke_then_401(client, pat):
    plain, headers, pid = pat
    # 吊销前能用
    r = client.post(
        "/api/v1/mcp",
        json=_rpc("initialize", {"protocolVersion": "2025-06-18"}),
        headers=headers,
    )
    assert r.status_code == 200, r.text
    # 吊销（幂等：连吊两次）
    assert client.delete(f"/api/v1/mcp/pats/{pid}", headers=AUTH).status_code == 204
    assert client.delete(f"/api/v1/mcp/pats/{pid}", headers=AUTH).status_code == 204
    # 吊销后立即 401
    r2 = client.post("/api/v1/mcp", json=_rpc("initialize", {}), headers=headers)
    assert r2.status_code == 401
    assert r2.headers["content-type"].startswith("application/problem+json")


def test_pat_patch_scopes(client, pat):
    _, headers, pid = pat
    r = client.patch(f"/api/v1/mcp/pats/{pid}", json={"scopes": ["notes:read"]}, headers=AUTH)
    assert r.status_code == 200
    assert r.json()["scopes"] == ["notes:read"]


# ───────────────────────── MCP 端点鉴权 ─────────────────────────
def test_mcp_requires_authorization(client):
    r = client.post("/api/v1/mcp", json=_rpc("initialize", {}))
    assert r.status_code == 401


def test_mcp_rejects_user_jwt(client):
    """用户 JWT 不能打 MCP 端点 —— AI 与人用不同凭证（ADR-0003 §2.3）。"""
    r = client.post("/api/v1/mcp", json=_rpc("initialize", {}), headers=AUTH)
    assert r.status_code == 401
    assert "PAT" in r.json()["detail"]


def test_mcp_rejects_fake_pat(client):
    r = client.post(
        "/api/v1/mcp", json=_rpc("initialize", {}),
        headers={"Authorization": f"Bearer {PAT_PREFIX}notarealtoken"},
    )
    assert r.status_code == 401


# ───────────────────────── 协议三原语 ─────────────────────────
def test_initialize(client, pat):
    _, headers, _ = pat
    r = client.post(
        "/api/v1/mcp",
        json=_rpc("initialize", {"protocolVersion": "2025-03-26"}),
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["result"]["protocolVersion"] == "2025-03-26"
    assert "tools" in body["result"]["capabilities"]
    assert body["result"]["serverInfo"]["name"] == "lifeos-mcp"


def test_notifications_return_202(client, pat):
    _, headers, _ = pat
    r = client.post(
        "/api/v1/mcp",
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        headers=headers,
    )
    assert r.status_code == 202
    assert r.content == b""


def test_tools_list_contains_calendar(client, pat):
    """磁盘上 calendar 的 manifest 有 provides → tools/list 必须出现（不重启）。"""
    _, headers, _ = pat
    r = client.post("/api/v1/mcp", json=_rpc("tools/list"), headers=headers)
    assert r.status_code == 200
    names = [t["name"] for t in r.json()["result"]["tools"]]
    assert "calendar_event_write" in names
    assert "calendar_event_read" in names
    assert "calendar_slot_free" in names


def test_unknown_method_rpc_error(client, pat):
    _, headers, _ = pat
    r = client.post("/api/v1/mcp", json=_rpc("no/such/method"), headers=headers)
    assert r.status_code == 200
    assert r.json()["error"]["code"] == -32601


def test_unknown_tool_rpc_error_and_audited(client, pat):
    _, headers, _ = pat
    r = client.post(
        "/api/v1/mcp",
        json=_rpc("tools/call", {"name": "ghost_tool_write", "arguments": {}}),
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["error"]["code"] == -32602
    # 拒绝也要留痕
    logs = client.get("/api/v1/mcp/audit-logs", headers=AUTH).json()
    assert any(entry["action"] == "denied" and "ghost" in entry["target"] for entry in logs)


def test_tools_call_scope_denied_403(client):
    """PAT 只有 calendar:read → 调写工具 calendar_event_write → 403 写明缺哪个 scope。"""
    r = client.post(
        "/api/v1/mcp/pats",
        json={"name": "只读-PAT", "scopes": ["calendar:read"]},
        headers=AUTH,
    )
    assert r.status_code == 201, r.text
    headers = {"Authorization": f"Bearer {r.json()['token']}"}
    r2 = client.post(
        "/api/v1/mcp",
        json=_rpc("tools/call", {"name": "calendar_event_write", "arguments": {}}),
        headers=headers,
    )
    assert r2.status_code == 403
    body = r2.json()
    assert "calendar:write" in body["detail"]


def test_tools_call_forwards_via_http(client, pat, monkeypatch):
    """成功路径：scope 过 → 内部 HTTP 转发（mock）→ 写类工具落审计。"""
    _, headers, _ = pat
    seen: dict = {}

    def fake_forward(method, path, payload, transport=None):
        seen.update(method=method, path=path, payload=payload)
        return 201, {"id": "abc123", "title": "被 AI 写进来的"}

    monkeypatch.setattr(mcp_server, "forward", fake_forward)
    payload = {"title": "被 AI 写进来的", "start_at": "2026-09-20T08:00:00+08:00",
               "end_at": "2026-09-20T09:00:00+08:00"}
    r = client.post(
        "/api/v1/mcp",
        json=_rpc("tools/call", {"name": "calendar_event_write",
                                 "arguments": {"payload": payload}}),
        headers=headers,
    )
    assert r.status_code == 200, r.text
    result = r.json()["result"]
    assert result["isError"] is False
    assert seen["method"] == "POST" and seen["path"] == "/api/v1/calendar/events"
    assert seen["payload"] == payload
    body = json.loads(result["content"][0]["text"])
    assert body["status"] == 201 and body["body"]["id"] == "abc123"
    # 写类工具 → audit_log 有 mcp 记录
    logs = client.get("/api/v1/mcp/audit-logs", headers=AUTH).json()
    assert any(e["action"] == "calendar_event_write" for e in logs)


def test_forward_mock_transport(monkeypatch):
    """forward 直测：MockTransport 注入（GET→params / POST→json）。"""
    from modules.mcp.forward import forward

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"echo_path": request.url.path,
                                         "q": dict(request.url.params)})

    code, body = forward("GET", "/api/v1/x/things", {"a": "1"},
                         transport=httpx.MockTransport(handler))
    assert code == 200 and body["q"]["a"] == "1"
    code, body = forward("GET", "/api/v1/x/things", None,
                         transport=httpx.MockTransport(handler))
    assert code == 200


# ───────────────────────── ★ 模块洁癖自检 ─────────────────────────
def test_mcp_module_purity():
    """modules/mcp/ 源码零业务词、零业务插件 import。

    与 scripts/check_kernel_purity.py 同款思路（AST 层，只看代码不看注释），
    但不改那个脚本（SCAN_ROOTS 扩围另走 issues 提卡）——先在本模块自守。
    docstring 里解释映射规则用的示例（如 calendar.event.write）不算违规——
    与内核洁癖检查器"剥掉注释与文档字符串"同一口径；但**代码与字符串字面量**
    不得出现业务词。
    """
    business_words = ("calendar", "todo", "notes", "finance", "habit",
                      "beecount", "obsidian", "diary")
    module_dir = Path(__file__).resolve().parents[1] / "modules" / "mcp"
    offenders: list[str] = []

    for py in sorted(module_dir.rglob("*.py")):
        if "__pycache__" in py.parts:
            continue
        src = py.read_text(encoding="utf-8")
        tree = ast.parse(src, filename=str(py))

        # 收集字符串常量占据的行号范围（docstring 也在其中，一并排除出行检查）；
        # 但除 docstring 外的字符串常量仍要做词检查 —— 先记范围，再按节点判断。
        string_line_ranges: list[tuple[int, int]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                string_line_ranges.append((node.lineno, node.end_lineno or node.lineno))

        def _in_string(lineno: int, _ranges=string_line_ranges) -> bool:
            return any(a <= lineno <= b for a, b in _ranges)

        def _is_modules_import(name: str) -> bool:
            return name.startswith("modules.") and not name.startswith("modules.mcp")

        for node in ast.walk(tree):
            # 1) 标识符不得含业务词
            if isinstance(node, ast.Name) and node.id.lower() in business_words:
                offenders.append(f"{py.name}:{node.lineno} 标识符 {node.id}")
            # 2) 字符串字面量（非 docstring 部分）不得含业务词。
            #    docstring 判定：位于模块/函数/类的 body 首位。
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if _is_docstring(node, tree):
                    continue
                v = node.value.lower()
                for w in business_words:
                    if w in v:
                        offenders.append(f"{py.name}:{node.lineno} 字符串 {node.value!r}")
            # 3) 严禁 import 其他插件模块
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if _is_modules_import(alias.name):
                        offenders.append(f"{py.name}:{node.lineno} import {alias.name}")
            if isinstance(node, ast.ImportFrom) and node.module and _is_modules_import(node.module):
                offenders.append(f"{py.name}:{node.lineno} from {node.module}")

        # 4) 代码行（去注释、去字符串行）不得含业务词 —— 兜住 f-string 片段等
        for i, line in enumerate(src.splitlines(), 1):
            if _in_string(i):
                continue
            code = line.split("#")[0].lower()
            for w in business_words:
                if w in code:
                    offenders.append(f"{py.name}:{i} 代码行含业务词 {w}")

    assert not offenders, "mcp 模块洁癖违规：\n" + "\n".join(offenders)


def _is_docstring(node: ast.Constant, tree: ast.AST) -> bool:
    """判定字符串常量是否是模块/类/函数的 docstring。"""
    parents: dict[int, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[id(child)] = parent
    owner = parents.get(id(node))
    if owner is None or not isinstance(owner, ast.Expr):
        return False
    body_owner = parents.get(id(owner))
    if body_owner is None:
        return False
    body = getattr(body_owner, "body", None)
    if not body:
        return False
    return body[0] is owner
