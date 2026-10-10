"""· href 白名单 + CRUD + 导出。"""
from __future__ import annotations

import os

os.environ.setdefault("DB_PATH", "./data/tmp_sidebar.db")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from core.app import create_app  # noqa: E402
from core.security import create_access_token  # noqa: E402
from db.engine import get_engine, init_engine  # noqa: E402
from modules.sidebar.models import SidebarItem  # noqa: E402
from modules.sidebar.schema import href_allowed  # noqa: E402

BASE = "/api/v1/sidebar"


@pytest.fixture(scope="module")
def client():
    init_engine()
    engine = get_engine()
    SidebarItem.__table__.create(bind=engine, checkfirst=True)
    app = create_app()
    c = TestClient(app)
    yield c
    engine.dispose()


@pytest.fixture
def auth():
    return {"Authorization": f"Bearer {create_access_token('admin')}"}


def test_href_whitelist_vectors():
    assert href_allowed("https://github.com")
    assert href_allowed("http://127.0.0.1:8000/app")
    assert href_allowed("  https://x  ".strip()) or href_allowed("https://x")
    assert not href_allowed("javascript:alert(1)")
    assert not href_allowed("data:text/html,x")
    assert not href_allowed("vbscript:msgbox")
    assert not href_allowed("//evil.com")
    assert not href_allowed("file:///etc/passwd")
    assert not href_allowed("")
    assert href_allowed("HTTPS://Example.COM")


def test_requires_auth(client):
    r = client.get(f"{BASE}/items")
    assert r.status_code == 401


def test_create_link_and_list(client, auth):
    r = client.post(
        f"{BASE}/items",
        headers=auth,
        json={"type": "link", "label": "GH", "href": "https://github.com", "abbr": "GH"},
    )
    assert r.status_code == 201, r.text
    iid = r.json()["id"]
    r2 = client.get(f"{BASE}/items", headers=auth)
    assert r2.status_code == 200
    assert r2.json()["count"] >= 1
    client.delete(f"{BASE}/items/{iid}", headers=auth)


def test_reject_bad_href(client, auth):
    r = client.post(
        f"{BASE}/items",
        headers=auth,
        json={"type": "link", "label": "bad", "href": "javascript:alert(1)"},
    )
    assert r.status_code == 422


def test_note_rejects_body(client, auth):
    r = client.post(
        f"{BASE}/items",
        headers=auth,
        json={"type": "note", "label": "便签", "body": "正文应走 node_ref"},
    )
    assert r.status_code == 422


def test_note_node_ref_ok(client, auth):
    r = client.post(
        f"{BASE}/items",
        headers=auth,
        json={"type": "note", "label": "便签", "node_ref": "notes/便签/x"},
    )
    assert r.status_code == 201, r.text
    iid = r.json()["id"]
    client.delete(f"{BASE}/items/{iid}", headers=auth)


def test_export(client, auth):
    r = client.get(f"{BASE}/export", headers=auth)
    assert r.status_code == 200
    assert "items" in r.json()
