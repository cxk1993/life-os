"""桥客户端：云侧签名请求本机桥（services/bridge）。

★ 签名算法必须与 services/bridge/protocol.py **逐字节一致**：
      f"{METHOD}|{path}|{ts}|{nonce}|{body}"
★ 只在 notes 插件内部使用；不 import 别的插件。
★ 超时要短（桥在本机，frp 隧道也应在秒级）；失败抛 BridgeError，由 service 转成 AppError。
"""
from __future__ import annotations

import hashlib
import hmac
import time
import uuid
from typing import Any

import httpx

from core.config import get_settings


# 与 bridge.protocol 同一 canonical 格式
def _canonical(method: str, path: str, ts: int, nonce: str, body: bytes) -> str:
    return f"{method.upper()}|{path}|{ts}|{nonce}|{body.decode('utf-8', 'replace')}"


def _sign(psk: str, method: str, path: str, ts: int, nonce: str, body: bytes = b"") -> str:
    msg = _canonical(method, path, ts, nonce, body).encode("utf-8")
    return hmac.new(psk.encode("utf-8"), msg, hashlib.sha256).hexdigest()


class BridgeError(Exception):
    """桥不可达 / 鉴权失败 / 返回异常。"""

    def __init__(self, detail: str, status: int = 502) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status = status


class BridgeClient:
    """对本机桥的签名 HTTP 客户端。path 必须带查询串（与桥侧 _canonical_path 一致）。"""

    def __init__(
        self,
        base_url: str | None = None,
        psk: str | None = None,
        timeout: float = 5.0,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or getattr(settings, "bridge_url", "") or "").rstrip("/")
        self.psk = psk or getattr(settings, "bridge_psk", "") or ""
        self.timeout = timeout

    def _headers(self, method: str, path: str, body: bytes = b"") -> dict[str, str]:
        if not self.psk:
            raise BridgeError("未配置 BRIDGE_PSK，无法访问本机桥", status=503)
        ts = int(time.time())
        nonce = uuid.uuid4().hex
        return {
            "X-Bridge-PSK": self.psk,
            "X-Bridge-Ts": str(ts),
            "X-Bridge-Nonce": nonce,
            "X-Bridge-Sign": _sign(self.psk, method, path, ts, nonce, body),
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        if not self.base_url:
            raise BridgeError("未配置 BRIDGE_URL", status=503)
        # 签名覆盖 path+query：先把 query 拼进 path 再签
        from urllib.parse import urlencode

        qs = urlencode({k: v for k, v in (params or {}).items() if v is not None})
        sign_path = path + (f"?{qs}" if qs else "")
        body = b""
        headers = self._headers(method, sign_path, body)
        url = self.base_url + sign_path
        try:
            resp = httpx.request(
                method, url, headers=headers, content=body or None, timeout=self.timeout
            )
        except httpx.HTTPError as exc:
            raise BridgeError(f"桥不可达：{exc}") from exc
        if resp.status_code >= 400:
            raise BridgeError(
                f"桥返回 {resp.status_code}：{resp.text[:200]}",
                status=502 if resp.status_code >= 500 else resp.status_code,
            )
        return resp.json()

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/bridge/healthz")

    def libs(self) -> list[dict[str, Any]]:
        data = self._request("GET", "/bridge/libs")
        return data if isinstance(data, list) else data.get("libs", [])

    def scan(self, lib: str, limit: int = 5000) -> list[dict[str, Any]]:
        """全量索引。桥侧是 ndjson 流；这里聚成 list（v0.1 库规模可控）。"""
        if not self.base_url:
            raise BridgeError("未配置 BRIDGE_URL", status=503)
        qs = f"lib={lib}&limit={limit}"
        sign_path = f"/bridge/scan?{qs}"
        headers = self._headers("GET", sign_path)
        try:
            resp = httpx.get(self.base_url + sign_path, headers=headers, timeout=self.timeout)
        except httpx.HTTPError as exc:
            raise BridgeError(f"桥不可达：{exc}") from exc
        if resp.status_code >= 400:
            raise BridgeError(f"桥返回 {resp.status_code}：{resp.text[:200]}")
        items: list[dict[str, Any]] = []
        for line in resp.text.splitlines():
            line = line.strip()
            if line:
                items.append(__import__("json").loads(line))
        return items

    def read(self, lib: str, path: str) -> dict[str, Any]:
        return self._request("GET", "/bridge/read", params={"lib": lib, "path": path})
