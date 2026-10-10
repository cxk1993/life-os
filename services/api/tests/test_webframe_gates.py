"""V9 WebFrame 安全判据骨架（W-1 / W-2）—— ★ 判据先行（astrbot）。

来源：astrbot《V9 安全判据·内嵌外部网页的六条硬判据》(2026-09-25 10:59)，
      「V9 六条硬判据全部采纳」「代写 W-1/W-2 单测骨架 ✅ 批准」。

现状：**WebFrame 内核接口未定稿**（归 ：`web.open(url, {profile, cache, persistLogin})`）。
      故本文件以 **skip 骨架**形式落地——接口定稿 + 实现后，去掉 skip 并补齐 `_call_web_open` 适配即可。

四层防线（入档）：
    服务端白名单（nginx `/ext/*` 非白名单 404） + 客户端白名单（`web.open` 调用即拒）
    + 沙箱（iframe sandbox） + 分区（cookie profile）
本文件覆盖 **客户端白名单层**（W-1/W-2）；服务端层由 hermes 执行 nginx 时验。

判据对照（六条硬判据 → 本文件覆盖）：
    W-1  白名单准入（host 必须在白名单，调用即拒）      ← 本文件
    W-2  协议白名单（仅 https；禁 http/javascript/data/file） ← 本文件
    W-3  iframe sandbox 属性白名单                      ← 前端（apps/web）
    W-4  登录态隔离（cookie 不互串）                     ← 前端 + B2 桥
    W-5  审计脱敏（记 host，不记 token/内容）            ← 与 BFF 审计共用 logger
    W-6  缓存边界（默认不缓存内容，显式开关）            ← 前端 + SW
"""
from __future__ import annotations

import pytest

# ★ 接口定稿前整体 skip。
#   实现落地后：删除下方 pytestmark，并在 `_call_web_open` 里接真实实现。
pytestmark = pytest.mark.skip(
    reason="V9 WebFrame 接口未定稿；定稿+实现后启用本骨架"
)


def _call_web_open(url: str) -> None:
    """★ 适配点：接真实 `web.open` 实现。

    预期契约（采纳）：
        web.open(url, *, profile=..., cache=..., persistLogin=...) -> handle
    白名单/协议校验应发生在**调用入口**（即本函数第一行），
    不合法则**立即抛错**（而非"打开后失败"）。
    """
    raise NotImplementedError("待 接口定稿后接入")


# ── W-1 · 白名单准入（调用即拒）──────────────────────────────────────────
def test_w1_non_whitelisted_host_rejected_on_call() -> None:
    """W-1：host 不在白名单 → **调用即拒**（不是打开后 404）。"""
    with pytest.raises(Exception):  # noqa: B017 - 具体异常类待接口定稿
        _call_web_open("https://evil.example.com/login")


def test_w1_whitelisted_host_accepted() -> None:
    """W-1：白名单内 host（BeeCount）→ 不抛错。"""
    _call_web_open("https://beecount.example.com:8443/login")


def test_w1_subdomain_spoof_rejected() -> None:
    """W-1：子域伪装（`beecount.example.com.evil.com`）→ 拒（后缀匹配陷阱）。"""
    with pytest.raises(Exception):  # noqa: B017
        _call_web_open("https://beecount.example.com.evil.com/")


# ── W-2 · 协议白名单（仅 https）──────────────────────────────────────────
@pytest.mark.parametrize(
    "url",
    [
        "http://beecount.example.com:8443/login",  # 明文 http
        "javascript:alert(1)",                          # 脚本执行
        "data:text/html,<script>alert(1)</script>",     # 内联文档
        "file:///etc/passwd",                           # 本机文件
    ],
)
def test_w2_dangerous_schemes_rejected(url: str) -> None:
    """W-2：仅允许 `https:`；四类危险协议（http/javascript/data/file）全拒。"""
    with pytest.raises(Exception):  # noqa: B017
        _call_web_open(url)


def test_w2_https_accepted() -> None:
    """W-2：https 通过（正例）。"""
    _call_web_open("https://beecount.example.com:8443/login")
