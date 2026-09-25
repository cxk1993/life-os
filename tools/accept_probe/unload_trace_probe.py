"""TX-VER-01 U-1..U-2 只读探针：卸载无痕迹核验（不写生产）。

用法：
  python tools/accept_probe/unload_trace_probe.py --module habits --base-url http://127.0.0.1:8000
"""
from __future__ import annotations

import argparse
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def get(url: str, token: str | None = None) -> tuple[int, str]:
    req = Request(url, headers={"Authorization": f"Bearer {token}"} if token else {})
    try:
        with urlopen(req, timeout=8) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except HTTPError as e:
        return int(e.code), e.read().decode("utf-8", "replace")
    except URLError as e:
        return 0, str(e)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--module", required=True)
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument("--token", default="")
    a = ap.parse_args()
    mod = a.module
    base = a.base_url.rstrip("/")

    st, body = get(f"{base}/api/v1/plugins", a.token or None)
    plugins: list = []
    if st == 200:
        try:
            data = json.loads(body)
            if isinstance(data, list):
                plugins = data
            elif isinstance(data, dict):
                plugins = data.get("items") or data.get("plugins") or []
        except json.JSONDecodeError:
            plugins = []
    u2 = not any(isinstance(p, dict) and str(p.get("id")) == mod for p in plugins)

    # U-1：业务路由应 404。★ 不用 /health——内核/发现层可能保留 health，
    # 以 list 主资源为准（habits→/habits，todo→/items，无表插件用 /manifest）。
    biz_path = {
        "habits": "habits",
        "todo": "items",
        "calendar": "events",
        "notes": "notes",
        "diary": "entries",
    }.get(mod, "manifest")
    st1, _ = get(f"{base}/api/v1/{mod}/{biz_path}", a.token or None)
    u1 = st1 == 404

    out = {
        "module": mod,
        "u1_route_404": u1,
        "u1_status": st1,
        "u2_dock_clean": u2,
        "u3_store": "manual-or-e2e",
        "u4_events": "manual-or-e2e",
        "pass": bool(u1 and u2),
        "note": (
            "pass 仅在【插件已禁用/卸载】后为 true；"
            "启用中预期 u1_status=401/200 且 pass=false（路由仍在=未卸干净）"
        ),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
