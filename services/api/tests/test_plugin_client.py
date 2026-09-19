"""ISSUE-005 A 案测试：get_plugin_client —— 插件间内部调用通道。

覆盖验收判据：
1. requires 含目标能力 → 返回 client（可调目标 API）
2. requires 不含目标能力 → 403 Forbidden（ADR-0002 声明即授权机器强制）
3. 非插件路径（无法识别 caller）→ 403
4. 新增函数不破坏现有 get_db/get_current_user（本测试自身依赖它们全绿即证明）

说明：get_plugin_client 是纯授权函数（不真发 HTTP），测试直接构造 Request
对象 + 手填 app.state.modules 验证授权逻辑，不依赖真实服务。
"""
from __future__ import annotations

import atexit
import os
import uuid
from contextlib import suppress
from typing import Any

_TMP_DB = f"./data/tmp_t18_{uuid.uuid4().hex[:8]}.db"
os.environ["DB_PATH"] = _TMP_DB


def _cleanup_tmp_db() -> None:
    with suppress(FileNotFoundError, PermissionError):
        os.remove(_TMP_DB)


atexit.register(_cleanup_tmp_db)

import pytest  # noqa: E402
from fastapi import FastAPI, Request  # noqa: E402

from core.app import create_app  # noqa: E402
from core.deps import InternalHttpClient, get_plugin_client  # noqa: E402
from core.errors import ForbiddenError  # noqa: E402


@pytest.fixture(scope="module")
def app() -> FastAPI:
    return create_app()


def _mk_request(app: FastAPI, path: str, token: str | None = None) -> Request:
    """构造一个指向某插件路径的假请求（带可选 Bearer token）。"""
    scope: dict[str, Any] = {
        "type": "http",
        "method": "GET",
        "path": path,
        "headers": [],
        "query_string": b"",
        "app": app,
    }
    if token:
        scope["headers"].append((b"authorization", f"Bearer {token}".encode()))
    return Request(scope)


@pytest.fixture(scope="module")
def token() -> str:
    from core.security import create_access_token

    return create_access_token("admin")


def test_requires_containing_capability_returns_client(app: FastAPI, token: str) -> None:
    """① diary 的 requires 含 docs.node.read → 授权通过，返回 InternalHttpClient。"""
    req = _mk_request(app, "/api/v1/diary/today", token)
    client = get_plugin_client(req, ["docs.node.read"])
    assert isinstance(client, InternalHttpClient)


def test_requires_missing_capability_403(app: FastAPI, token: str) -> None:
    """② diary 的 requires 不含 review.read → 403 Forbidden（声明即授权）。"""
    req = _mk_request(app, "/api/v1/diary/today", token)
    with pytest.raises(ForbiddenError) as exc:
        get_plugin_client(req, ["review.read"])
    assert "未声明能力" in str(exc.value)
    assert "review.read" in str(exc.value)


def test_non_plugin_path_403(app: FastAPI, token: str) -> None:
    """③ 内核路径（非插件）→ 无法识别 caller → 403。"""
    req = _mk_request(app, "/api/v1/modules", token)
    with pytest.raises(ForbiddenError) as exc:
        get_plugin_client(req, ["docs.node.read"])
    assert "无法识别调用方插件" in str(exc.value)


def test_missing_bearer_403(app: FastAPI, token: str) -> None:
    """④ 插件路径但请求头无 token → 403（不能签发内部调用 token）。"""
    req = _mk_request(app, "/api/v1/diary/today")  # 无 token
    with pytest.raises(ForbiddenError) as exc:
        get_plugin_client(req, ["docs.node.read"])
    assert "缺少 Bearer token" in str(exc.value)


def test_multiple_capabilities_all_required(app: FastAPI, token: str) -> None:
    """⑤ 请求多个能力，全部在 requires 内 → 通过。"""
    req = _mk_request(app, "/api/v1/diary/today", token)
    client = get_plugin_client(
        req, ["docs.node.read", "docs.node.write", "docs.search"]
    )
    assert isinstance(client, InternalHttpClient)


def test_partial_missing_403(app: FastAPI, token: str) -> None:
    """⑥ 请求多个能力，部分不在 requires → 403（列出缺失的）。"""
    req = _mk_request(app, "/api/v1/diary/today", token)
    with pytest.raises(ForbiddenError) as exc:
        get_plugin_client(req, ["docs.node.read", "calendar.event.read"])
    assert "calendar.event.read" in str(exc.value)
