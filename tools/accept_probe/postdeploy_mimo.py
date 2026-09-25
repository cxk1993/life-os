#!/usr/bin/env python3
"""令106 · MiMo 部署后真机回测：O1 四态 / sidebar 增删 / habits 增减 / N2 + retest13。

用法（部署完成后）：
  python tools/accept_probe/postdeploy_mimo.py --base-url https://life.example.com:8443 [--token JWT]

只读 GET 为主；sidebar/habits 增删在带 token 时做「建-查-删」自洽环（不留垃圾）。
"""
from __future__ import annotations

import argparse
import json
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def req(method: str, url: str, token: str = "", body: dict | None = None) -> tuple[int, str]:
    data = json.dumps(body).encode() if body is not None else None
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        headers["Content-Type"] = "application/json"
    r = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(r, timeout=15) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except HTTPError as e:
        return int(e.code), e.read().decode("utf-8", "replace")
    except URLError as e:
        return 0, str(e)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="https://life.example.com:8443")
    ap.add_argument("--token", default="")
    a = ap.parse_args()
    base = a.base_url.rstrip("/")
    tok = a.token
    rows: list[dict] = []

    def rec(item: str, ok: bool, detail: str) -> None:
        rows.append({"item": item, "ok": ok, "detail": detail})

    # O1 四态：health/modules（dock 四态）
    st, body = req("GET", f"{base}/api/v1/health/modules", tok)
    ok_o1 = st == 200 and ("healthy" in body or "degraded" in body or "unknown" in body)
    rec("O1 四态", ok_o1, f"HTTP {st}")

    # N2：提醒策略模块在（calendar health）
    st, _ = req("GET", f"{base}/api/v1/calendar/health", tok)
    rec("N2/calendar", st == 200, f"HTTP {st}")

    # sidebar 增删环
    label = f"probe-{uuid.uuid4().hex[:8]}"
    st, body = req(
        "POST",
        f"{base}/api/v1/sidebar/items",
        tok,
        {"type": "link", "label": label, "href": "https://example.com", "group": "probe"},
    )
    created = st == 201
    rec("sidebar 增", created, f"HTTP {st}")
    iid = ""
    if created:
        try:
            iid = json.loads(body).get("id") or ""
        except json.JSONDecodeError:
            iid = ""
    if iid:
        st, _ = req("DELETE", f"{base}/api/v1/sidebar/items/{iid}", tok)
        rec("sidebar 删", st in (200, 204), f"HTTP {st}")
    else:
        rec("sidebar 删", False, "no id")

    # habits 增删环
    hname = f"probe-{uuid.uuid4().hex[:8]}"
    st, body = req("POST", f"{base}/api/v1/habits/habits", tok, {"name": hname})
    hok = st == 201
    rec("habits 增", hok, f"HTTP {st}")
    hid = ""
    if hok:
        try:
            hid = json.loads(body).get("id") or ""
        except json.JSONDecodeError:
            hid = ""
    if hid:
        st, _ = req("DELETE", f"{base}/api/v1/habits/habits/{hid}", tok)
        rec("habits 删", st in (200, 204), f"HTTP {st}")
    else:
        rec("habits 删", False, "no id")

    # retest13 核心端点（notes 真路由=/libs，不是 /tree）
    for p in (
        "/api/v1/calendar/today-summary",
        "/api/v1/todo/today-summary",
        "/api/v1/notes/libs",
    ):
        st, _ = req("GET", base + p, tok)
        rec(p, st in (200, 401), f"HTTP {st}")

    out = {"rows": rows, "fail_count": sum(1 for r in rows if not r["ok"])}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["fail_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
