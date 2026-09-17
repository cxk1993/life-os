"""桥请求签名与校验（HMAC-SHA256 + PSK + 时间戳 + nonce）。

★ 同一套算法，本机桥（校验侧）与云服务器（签名侧，见 services/api/modules/notes/bridge_client.py）
  都必须实现，且 canonical string 的格式完全一致：

      f"{method.upper()}|{path}|{ts}|{nonce}|{body}"

  这样两侧才能对得上。

★ 五道闸门（验收项逐条对应）：
  1. 缺 / 错 X-Bridge-PSK        → 无 PSK / 错 PSK
  2. 签名对不上（X-Bridge-Sign） → 错签名（哪怕 PSK 对了，body 被改也拒）
  3. 时间戳偏差 > 60s            → 过期时间戳
  4. nonce 5 分钟内重现           → 重放攻击
  5. 路径穿越                     → 400（见 reader.py，不在本协议内）

★ 安全铁律：日志里只记录 nonce 前 8 位与校验结果，绝不打印 PSK / 明文签名 / 完整 body。
"""
from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any

TS_TOLERANCE_S = 60
NONCE_TTL_S = 300


def _to_bytes(x: Any) -> bytes:
    if isinstance(x, bytes):
        return x
    return str(x).encode("utf-8")


def canonical_string(
    method: str,
    path: str,
    ts: str | int,
    nonce: str,
    body: bytes | str = b"",
) -> str:
    """构造待签名字符串。path 必须是**规范化后**的路径（不含查询串）。"""
    return f"{method.upper()}|{path}|{ts}|{nonce}|{_to_bytes(body).decode('utf-8', 'replace')}"


def sign(
    psk: str,
    method: str,
    path: str,
    ts: str | int,
    nonce: str,
    body: bytes | str = b"",
) -> str:
    msg = canonical_string(method, path, ts, nonce, body).encode("utf-8")
    return hmac.new(_to_bytes(psk), msg, hashlib.sha256).hexdigest()


def verify_sig(
    psk: str,
    method: str,
    path: str,
    ts: str | int,
    nonce: str,
    signature: str,
    body: bytes | str = b"",
) -> bool:
    """常量时间比较，避免时序侧信道。"""
    expected = sign(psk, method, path, ts, nonce, body)
    return hmac.compare_digest(expected, signature)


def check_timestamp(ts_raw: str | int | None) -> int:
    """校验时间戳新鲜度；返回解析后的整数秒，偏差超 60s 抛 ValueError。"""
    if ts_raw is None:
        raise ValueError("缺少时间戳")
    try:
        ts = int(ts_raw)
    except (TypeError, ValueError):
        raise ValueError("时间戳不是整数")
    now = int(time.time())
    if abs(now - ts) > TS_TOLERANCE_S:
        raise ValueError(f"时间戳偏差超过 {TS_TOLERANCE_S}s（now={now}, ts={ts}）")
    return ts


class NonceStore:
    """近期见过的 nonce；TTL 5 分钟，自动过期清理（防重放）。"""

    def __init__(self, ttl: int = NONCE_TTL_S) -> None:
        self._seen: dict[str, int] = {}
        self._ttl = ttl

    def _prune(self, now: int) -> None:
        expired = [n for n, t in self._seen.items() if now - t > self._ttl]
        for n in expired:
            self._seen.pop(n, None)

    def seen(self, nonce: str) -> bool:
        now = int(time.time())
        self._prune(now)
        return nonce in self._seen

    def add(self, nonce: str) -> None:
        self._seen[nonce] = int(time.time())
