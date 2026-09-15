"""空壳冒烟测试。

T01 的验收要求：`make test` 在空项目上也要通过（不是"没有测试"）。
所以这里有一条真实可跑的测试，而不是占位符。
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_healthz_returns_ok() -> None:
    """总纲验收口径：/healthz 必须返回 {"ok": true}。"""
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
