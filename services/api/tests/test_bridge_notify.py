"""T24 桥通知端点与通知历史测试（只读协议+notify，不碰真实 Windows 弹窗）。"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# bridge 包在 services/ 下，与 services/api 测试根并列
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # services/

from bridge.config import BridgeConfig, Lib  # noqa: E402
from bridge.main import create_bridge_app  # noqa: E402
from bridge.notify import NotifyResult, send_windows_notification  # noqa: E402
from bridge.protocol import sign  # noqa: E402

PSK = "test-psk-t24"


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    lib = Lib(id="t", name="tmp", path=str(tmp_path), mode="ro", enabled=True)
    cfg = BridgeConfig(psk=PSK, libs=[lib])
    app = create_bridge_app(config=cfg)
    return TestClient(app)


def _auth_headers(method: str, path: str, body: bytes = b"") -> dict[str, str]:
    ts = int(time.time())
    nonce = f"n-{ts}-{len(body)}-{path}"
    sig = sign(PSK, method, path, ts, nonce, body)
    return {
        "X-Bridge-PSK": PSK,
        "X-Bridge-Ts": str(ts),
        "X-Bridge-Nonce": nonce,
        "X-Bridge-Sign": sig,
    }


def test_notify_requires_auth(client: TestClient) -> None:
    r = client.post("/bridge/notify", json={"title": "t", "body": "b"})
    assert r.status_code == 401


def test_notify_empty_body_rejected(client: TestClient) -> None:
    payload = json.dumps({"title": "t", "body": "  "}, ensure_ascii=False).encode()
    headers = _auth_headers("POST", "/bridge/notify", payload)
    r = client.post("/bridge/notify", content=payload, headers=headers)
    assert r.status_code == 400
    assert "body" in r.json()["detail"]


def test_notify_invalid_json(client: TestClient) -> None:
    body = b"not-json"
    headers = _auth_headers("POST", "/bridge/notify", body)
    r = client.post("/bridge/notify", content=body, headers=headers)
    assert r.status_code == 400


def test_notify_log_channel_success_and_history(client: TestClient) -> None:
    payload = json.dumps(
        {"title": "日程提醒", "body": "20:00 测试提醒", "channel": "log"},
        ensure_ascii=False,
    ).encode()
    headers = _auth_headers("POST", "/bridge/notify", payload)
    r = client.post("/bridge/notify", content=payload, headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["channel"] == "log"
    assert data["id"] >= 1

    h = _auth_headers("GET", "/bridge/notifications")
    r2 = client.get("/bridge/notifications", headers=h)
    assert r2.status_code == 200
    items = r2.json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "日程提醒"
    assert items[0]["body_len"] == len("20:00 测试提醒")


def test_healthz_advertises_notify_capability(client: TestClient) -> None:
    headers = _auth_headers("GET", "/bridge/healthz")
    r = client.get("/bridge/healthz", headers=headers)
    assert r.status_code == 200
    assert "notify" in r.json()["capabilities"]


def test_send_windows_notification_log_channel() -> None:
    result = send_windows_notification("标题", "内容", channel="log")
    assert isinstance(result, NotifyResult)
    assert result.ok is True
    assert result.channel == "log"


def test_send_windows_notification_empty_body() -> None:
    result = send_windows_notification("标题", "   ", channel="log")
    assert result.ok is False
