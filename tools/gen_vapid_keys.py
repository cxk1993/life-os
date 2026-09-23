#!/usr/bin/env python
"""生成 VAPID 密钥对（Web Push · push 插件用）。

用法（在 services/api 的 venv 里跑，因为要 import py_vapid）：

    python tools/gen_vapid_keys.py                 # 默认 dry-run：只打印公钥 + 写入指引
    python tools/gen_vapid_keys.py --write         # 写入 <repo>/.env（幂等替换三键）
    python tools/gen_vapid_keys.py --env /path/.env --write   # 指定目标 .env（运维/生产）

★ 格式（L1 源码取证：py_vapid.Vapid.from_string 去换行后 b64urldecode，32 字节走 from_raw）：
- PUSH_VAPID_PUBLIC_KEY  = 未压缩公钥点（65 字节、0x04 开头）的 base64url
                           —— 前端 pushManager.subscribe 的 applicationServerKey 正是此形状
- PUSH_VAPID_PRIVATE_KEY = 32 字节私钥标量的 base64url（from_string → from_raw）
- 一律 base64url 去 padding、单行（.env 的值不能跨行）

★ 安全：
- 私钥**永不打印**；dry-run 也只打印公钥（公钥本就该公开，前端要拿它）
- 落盘只进 .env（.gitignore 已忽略 `.env` / `.env.*`）；绝不入库、绝不落帖
- 生成后**自验三项**：from_string 可反解 / 公私钥配对 / 公钥形状合规
"""
from __future__ import annotations

import argparse
import base64
import pathlib
import sys

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid  # type: ignore[import-untyped]

KEYS = ("PUSH_VAPID_PUBLIC_KEY", "PUSH_VAPID_PRIVATE_KEY", "PUSH_VAPID_CLAIMS_EMAIL")
DEFAULT_ENV = pathlib.Path(__file__).resolve().parents[1] / ".env"


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def main() -> int:
    ap = argparse.ArgumentParser(description="生成 VAPID 密钥对（Web Push）")
    ap.add_argument("--env", default=str(DEFAULT_ENV), help="目标 .env 路径（默认 <repo>/.env）")
    ap.add_argument("--write", action="store_true", help="写入 .env（默认只 dry-run 打印公钥）")
    ap.add_argument("--claims-email", default="mailto:admin@localhost", help="VAPID claims sub")
    args = ap.parse_args()

    v = Vapid()
    v.generate_keys()

    pub_raw = v.public_key.public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    priv_raw = v.private_key.private_numbers().private_value.to_bytes(32, "big")
    pub_b64, priv_b64 = b64url(pub_raw), b64url(priv_raw)

    # 自验
    try:
        back = Vapid.from_string(priv_b64)
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: 私钥 from_string 反解失败：{exc}", file=sys.stderr)
        return 1
    back_pub = b64url(
        back.public_key.public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
        )
    )
    if back_pub != pub_b64:
        print("FAIL: 公私钥不配对", file=sys.stderr)
        return 1
    if len(pub_raw) != 65 or pub_raw[0] != 0x04:
        print(f"FAIL: 公钥形状异常 len={len(pub_raw)} head={pub_raw[0]:#x}", file=sys.stderr)
        return 1

    print("✅ 自验通过：from_string 可反解 · 公私钥配对 · 公钥形状 65B/0x04")
    print(f"PUSH_VAPID_PUBLIC_KEY={pub_b64}")
    print("PUSH_VAPID_PRIVATE_KEY=<hidden —— 不打印>")

    if not args.write:
        print("\n（dry-run）加 --write 才会落盘到 .env")
        return 0

    env_path = pathlib.Path(args.env)
    if not env_path.exists():
        print(f"FAIL: 目标 .env 不存在：{env_path}", file=sys.stderr)
        return 1

    lines = env_path.read_text(encoding="utf-8").splitlines()
    kept = [ln for ln in lines if not any(ln.startswith(k + "=") for k in KEYS)]
    while kept and not kept[-1].strip():
        kept.pop()
    kept += [
        "",
        "# ── Web Push（push 插件 · base64url 单行 · 由 tools/gen_vapid_keys.py 生成）──",
        "# ★ 私钥只在本文件与服务端 .env；绝不入库（.gitignore 已忽略）、绝不落帖",
        f"{KEYS[0]}={pub_b64}",
        f"{KEYS[1]}={priv_b64}",
        f"{KEYS[2]}={args.claims_email}",
    ]
    env_path.write_text("\n".join(kept) + "\n", encoding="utf-8")

    chk = env_path.read_text(encoding="utf-8")
    ok = all(f"{k}=" in chk for k in KEYS)
    print(f"\n{'✅' if ok else '❌'} 已写入 {env_path}（三键齐备={ok}）")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
