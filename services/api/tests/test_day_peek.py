"""U2 day_peek / day_dots 测试（只读聚合 + 软失败）。"""
from __future__ import annotations

import os

os.environ["DB_PATH"] = "./data/tmp_day_peek.db"

from datetime import date, datetime, timezone  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from core.app import create_app  # noqa: E402
from core.security import create_access_token  # noqa: E402
from db.engine import get_engine, init_engine  # noqa: E402
from db.base import SQLModel  # noqa: E402


def test_day_peek_shape(client_auth):
    client, auth = client_auth
    r = client.get("/api/v1/dashboard/day-peek?date=2026-09-23", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["date"] == "2026-09-23"
    assert set(body["marks"]) == {"calendar", "diary", "review", "todo_open"}
    assert set(body["dots"]) == {"has_event", "has_diary", "has_review", "has_todo"}
    assert set(body["list"]) == {"calendar", "diary", "review", "todo"}


def test_day_dots_shape(client_auth):
    client, auth = client_auth
    r = client.get("/api/v1/dashboard/day-dots?from=2026-09-01&to=2026-09-30", headers=auth)
    assert r.status_code == 200
    assert isinstance(r.json(), dict)


def test_day_peek_requires_auth(client_auth):
    client, _ = client_auth
    assert client.get("/api/v1/dashboard/day-peek").status_code == 401


def test_day_peek_soft_fail_empty(client_auth):
    client, auth = client_auth
    body = client.get("/api/v1/dashboard/day-peek?date=2020-01-01", headers=auth).json()
    assert body["marks"]["calendar"] == 0
    assert body["dots"]["has_event"] is False


@pytest.fixture(scope="module")
def client_auth():
    init_engine()
    SQLModel.metadata.create_all(get_engine())
    client = TestClient(create_app())
    auth = {"Authorization": f"Bearer {create_access_token('admin')}"}
    yield client, auth
