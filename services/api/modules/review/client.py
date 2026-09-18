"""Work-Review 上游客户端（只读）。

★ 铁律：对 Work-Review **只读**，禁止任何写 HTTP。
★ 凭据只从环境变量读，禁止写进代码/前端/git：
    REVIEW_UPSTREAM       mock | api（默认 mock，离线测试全绿）
    WORK_REVIEW_BASE_URL  默认 http://127.0.0.1:49996（★ 不是 47831）
    WORK_REVIEW_TOKEN     Bearer token（api 模式必填）
    WORK_REVIEW_BRIDGE    true 时按桥语义处理失败（快速失败「桥离线」）
★ 桥/frp 传输本卡不实现：BRIDGE=true 仅影响错误语义与超时。
"""
from __future__ import annotations

import hashlib
import os
import re
from datetime import date as DateType
from datetime import timedelta
from typing import Any

import httpx

from .parser import parse_duration

DEFAULT_BASE_URL = "http://127.0.0.1:49996"
BRIDGE_TIMEOUT = 3.0
DIRECT_TIMEOUT = 5.0

MOCK_VERSION = "1.0.56"
MOCK_HEALTH = {
    "paused": False,
    "recording": True,
    "status": "ok",
    "version": MOCK_VERSION,
}

_CATEGORY_POOL = ["编码", "会议", "文档", "沟通", "学习", "杂务"]
_APP_POOL = ["Code.exe", "WorkBuddy", "Xiaomi MiMo", "chrome.exe", "Obsidian.exe", "WeChat"]
_DOMAIN_POOL = ["github.com", "docs.python.org", "juejin.cn", "stackoverflow.com"]


class ReviewUpstreamError(Exception):
    """上游不可达 / token 无效 / 返回异常。"""

    def __init__(self, detail: str, status: int = 502) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status = status


class BridgeOfflineError(ReviewUpstreamError):
    """WORK_REVIEW_BRIDGE=true 且桥不可达。前端应显示「桥离线」，不转圈。"""

    def __init__(self, detail: str = "桥离线") -> None:
        super().__init__(detail, status=503)


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def _env_bool(name: str, default: bool = False) -> bool:
    raw = _env(name).lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def _day_seed(d: DateType) -> int:
    """确定性伪随机：同一日期永远得到同一套 mock，便于测试与趋势对比。"""
    h = hashlib.md5(d.isoformat().encode("utf-8")).hexdigest()
    return int(h[:8], 16)


def _fmt_cn(seconds: int) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    parts: list[str] = []
    if h:
        parts.append(f"{h}小时")
    if m:
        parts.append(f"{m}分")
    if s or not parts:
        parts.append(f"{s}秒")
    return "".join(parts)


def _mk_rows(names: list[str], base_seconds: list[int], seed: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for i, name in enumerate(names):
        wobble = ((seed >> (i * 3)) % 17) * 60  # 0~16 分钟抖动
        sec = max(30, base_seconds[i] + wobble)
        rows.append({"name": name, "seconds": sec, "duration_text": _fmt_cn(sec)})
    return rows


def mock_report(date: DateType) -> dict[str, Any]:
    """内置合理假数据（类别/应用/网站/小时/AI）。离线可测，趋势有变化。"""
    seed = _day_seed(date)
    weekday = date.weekday()
    empty_day = seed % 11 == 0  # 偶发空日，覆盖「当日无记录」路径

    if empty_day:
        return {
            "date": date.isoformat(),
            "empty": True,
            "categories": [],
            "apps": [],
            "domains": [],
            "hourly": [{"hour": h, "seconds": 0} for h in range(24)],
            "ai_analysis_md": "",
        }

    coding = 3 * 3600 + 13 * 60 + 52 - weekday * 180
    meeting = 41 * 60 + 13 + weekday * 90
    doc = 29 + (seed % 5) * 120
    base_cat = [max(coding, 600), max(meeting, 300), max(doc, 30), 1200, 900, 400]
    categories = _mk_rows(_CATEGORY_POOL, base_cat, seed)

    base_app = [7200, 3600, 2400, 1800, 1200, 600]
    apps = _mk_rows(_APP_POOL, base_app, seed + 3)

    base_dom = [1800, 1200, 900, 600]
    domains = _mk_rows(_DOMAIN_POOL, base_dom, seed + 7)

    hourly: list[dict[str, Any]] = []
    for h in range(24):
        if 9 <= h <= 18:
            sec = 1200 + ((seed + h * 37) % 40) * 30
        elif 20 <= h <= 22:
            sec = 300 + ((seed + h) % 10) * 30
        else:
            sec = ((seed + h * 13) % 7) * 20
        hourly.append({"hour": h, "seconds": sec, "duration_text": _fmt_cn(sec)})

    top = categories[0]["name"] if categories else "编码"
    ai = (
        f"## AI 分析 · {date.isoformat()}\n\n"
        f"- 今日主力：**{top}**（{_fmt_cn(categories[0]['seconds'])}）\n"
        f"- 应用 Top1：{apps[0]['name'] if apps else '—'}\n"
        f"- 建议：保持深度工作块，会议尽量合并。\n"
    )

    return {
        "date": date.isoformat(),
        "empty": False,
        "categories": categories,
        "apps": apps,
        "domains": domains,
        "hourly": hourly,
        "ai_analysis_md": ai,
    }


def mock_markdown(date: DateType) -> str:
    """按 WR_BLOCK 标记生成 export-markdown 假原文（与解析器同款格式）。"""
    report = mock_report(date)
    if report.get("empty"):
        return f"# 工作日报 {date.isoformat()}\n\n当日无记录。\n"

    def _table(title: str, key: str, col: str) -> str:
        rows = report.get(key) or []
        lines = [
            f"<!-- WR_BLOCK_START:{title} -->",
            f"| {col} | 时长 |",
            "|:--|:--|",
        ]
        for r in rows:
            lines.append(f"| {r['name']} | {r.get('duration_text', '')} |")
        lines.append(f"<!-- WR_BLOCK_END:{title} -->")
        return "\n".join(lines)

    hourly_lines = [
        "<!-- WR_BLOCK_START:HOURLY_SUMMARY -->",
        "| 小时 | 时长 |",
        "|:--|:--|",
    ]
    for r in report.get("hourly") or []:
        if r.get("seconds"):
            dur_h = r.get("duration_text") or _fmt_cn(r["seconds"])
            hourly_lines.append(f"| {r['hour']} | {dur_h} |")
    hourly_lines.append("<!-- WR_BLOCK_END:HOURLY_SUMMARY -->")

    parts = [
        f"# 工作日报 {date.isoformat()}\n",
        _table("CATEGORY_TABLE", "categories", "类别"),
        _table("APP_USAGE_TABLE", "apps", "应用"),
        _table("DOMAIN_USAGE_TABLE", "domains", "网站"),
        "\n".join(hourly_lines),
        "<!-- WR_BLOCK_START:AI_ANALYSIS -->",
        str(report.get("ai_analysis_md") or ""),
        "<!-- WR_BLOCK_END:AI_ANALYSIS -->",
    ]
    return "\n\n".join(parts) + "\n"


def mock_weekly(date: DateType) -> dict[str, Any]:
    """内置周报假数据（不落库，实时代理时用）。"""
    start = date - timedelta(days=date.weekday())
    days = []
    total = 0
    for i in range(7):
        d = start + timedelta(days=i)
        r = mock_report(d)
        day_total = sum(c["seconds"] for c in r.get("categories") or [])
        if r.get("empty"):
            day_total = 0
        total += day_total
        days.append({"date": d.isoformat(), "total_seconds": day_total})
    return {
        "week_start": start.isoformat(),
        "week_end": (start + timedelta(days=6)).isoformat(),
        "date": date.isoformat(),
        "total_seconds": total,
        "days": days,
        "summary": f"本周合计 {_fmt_cn(total)}，来自 Work-Review mock 周报。",
        "source": "mock",
    }


class ReviewClient:
    """对 Work-Review Localhost API 的只读客户端（api 模式）/ 内置假数据（mock 模式）。"""

    def __init__(
        self,
        mode: str | None = None,
        base_url: str | None = None,
        token: str | None = None,
        bridge: bool | None = None,
        timeout: float | None = None,
    ) -> None:
        self.mode = (mode or _env("REVIEW_UPSTREAM", "mock")).lower()
        if self.mode not in ("mock", "api"):
            self.mode = "mock"
        self.base_url = (
            base_url or _env("WORK_REVIEW_BASE_URL", DEFAULT_BASE_URL)
        ).rstrip("/")
        self.token = token if token is not None else _env("WORK_REVIEW_TOKEN")
        self.bridge = _env_bool("WORK_REVIEW_BRIDGE", False) if bridge is None else bridge
        if timeout is not None:
            self.timeout = timeout
        else:
            self.timeout = BRIDGE_TIMEOUT if self.bridge else DIRECT_TIMEOUT

    # ───────────────────────── 配置态 ─────────────────────────
    @property
    def path_kind(self) -> str:
        """取数路径：direct（同机直连）| bridge（经桥/frp 转发）| mock。"""
        if self.mode == "mock":
            return "mock"
        return "bridge" if self.bridge else "direct"

    def require_token_for_api(self) -> None:
        if self.mode == "api" and not self.token:
            raise ReviewUpstreamError(
                "WORK_REVIEW_TOKEN 未配置，无法访问 Work-Review（token 只从环境变量读）",
                status=503,
            )

    # ───────────────────────── HTTP ─────────────────────────
    def _headers(self) -> dict[str, str]:
        self.require_token_for_api()
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }

    def _map_error(self, exc: Exception) -> ReviewUpstreamError:
        if self.bridge:
            return BridgeOfflineError(f"桥离线：{type(exc).__name__}")
        return ReviewUpstreamError(f"Work-Review 不可达：{exc}", status=502)

    def _map_status(self, status_code: int, text: str) -> ReviewUpstreamError:
        if status_code in (401, 403):
            return ReviewUpstreamError(
                "Work-Review 不可达 / token 无效", status=503
            )
        if self.bridge and status_code >= 500:
            return BridgeOfflineError(f"桥离线：上游 {status_code}")
        return ReviewUpstreamError(
            f"Work-Review 返回 {status_code}：{text[:200]}", status=502
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        if self.mode == "mock":
            raise ReviewUpstreamError("mock 模式不应发起真实 HTTP", status=500)
        self.require_token_for_api()
        url = f"{self.base_url}{path}"
        try:
            resp = httpx.request(
                method,
                url,
                headers=self._headers(),
                json=json_body,
                params=params,
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise self._map_error(exc) from exc
        if resp.status_code >= 400:
            raise self._map_status(resp.status_code, resp.text)
        if not resp.content:
            return {}
        try:
            return resp.json()
        except ValueError:
            return {"raw": resp.text}

    # ───────────────────────── 业务只读端点 ─────────────────────────
    def health(self) -> dict[str, Any]:
        """连通自检：api 透传 GET /health；mock 返回内置健康包。"""
        if self.mode == "mock":
            return {**MOCK_HEALTH, "mode": "mock"}
        data = self._request("GET", "/health")
        if not isinstance(data, dict) or "version" not in data:
            raise ReviewUpstreamError("Work-Review 不可达 / token 无效（health 无 version）", 503)
        return data

    def get_report(self, date: DateType) -> dict[str, Any]:
        """结构化日报（主力落库源）。"""
        if self.mode == "mock":
            return mock_report(date)
        return self._request("GET", f"/v1/reports/{date.isoformat()}")

    def export_markdown(self, date: DateType) -> str:
        """导出 Markdown 日报原文（raw_md 来源）。只读调用。

        实测（v1.0.56）：POST /v1/reports/export-markdown 常只返回落盘路径
        `{"path":"...\\日报\\YYYY-MM-DD.md"}`，**不直接回 markdown 正文**。
        铁律禁止我们 open() 读盘 → 此时回退到 GET /v1/reports/{date} 的
        `content` 字段（仍是 API 拿到的原文，不是猜文件目录）。
        """
        if self.mode == "mock":
            return mock_markdown(date)
        data = self._request(
            "POST",
            "/v1/reports/export-markdown",
            json_body={"date": date.isoformat()},
        )
        if isinstance(data, str):
            s = data.strip()
            if s and not s.startswith("{") and "path" not in s[:20]:
                return data
        if isinstance(data, dict):
            for key in ("markdown", "content", "text", "raw", "md"):
                val = data.get(key)
                if isinstance(val, str) and len(val.strip()) > 40:
                    return val
            if "path" in data:
                report = self.get_report(date)
                if isinstance(report, dict) and isinstance(report.get("content"), str):
                    return str(report["content"])
        return ""

    def get_hourly(self, date: DateType) -> list[dict[str, Any]]:
        if self.mode == "mock":
            return list(mock_report(date).get("hourly") or [])
        data = self._request("GET", f"/v1/hourly-summaries/{date.isoformat()}")
        raw_list: list[Any] = []
        if isinstance(data, list):
            raw_list = data
        elif isinstance(data, dict):
            for key in ("hourly", "summaries", "items", "data"):
                val = data.get(key)
                if isinstance(val, list):
                    raw_list = val
                    break
        out: list[dict[str, Any]] = []
        for item in raw_list:
            if not isinstance(item, dict):
                continue
            hour = item.get("hour")
            try:
                h = int(hour)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                continue
            dur = item.get("duration_text") or item.get("duration")
            sec = item.get("seconds")
            if sec is None:
                # 实测字段可能是 summary 文本（含「4分钟」），从摘要抽时长
                sec = parse_duration(dur) or parse_duration(str(item.get("summary") or ""))
            out.append(
                {
                    "hour": h,
                    "seconds": int(sec or 0),
                    "duration_text": str(dur or ""),
                    "summary": str(item.get("summary") or ""),
                }
            )
        return out

    def get_weekly_review(self, date: DateType) -> dict[str, Any]:
        if self.mode == "mock":
            return mock_weekly(date)
        data = self._request(
            "GET", "/v1/weekly-review", params={"date": date.isoformat()}
        )
        if not isinstance(data, dict):
            return {"raw": data, "date": date.isoformat(), "source": "api"}
        # 已是结构化
        if "total_seconds" in data or "days" in data:
            data.setdefault("source", "api")
            return data
        # 实测：{title, markdown} —— 从 markdown 抽总时长
        md = str(data.get("markdown") or data.get("content") or "")
        m = re.search(r"总投入时长[：:]\s*([0-9小时分秒]+)", md)
        total = parse_duration(m.group(1)) if m else 0
        summary = str(data.get("title") or "")
        if m:
            summary = f"{summary} · 总投入 {m.group(1)}" if summary else f"总投入 {m.group(1)}"
        return {
            "date": date.isoformat(),
            "week_start": None,
            "week_end": None,
            "total_seconds": total,
            "days": [],
            "summary": summary or md[:120],
            "source": "api",
            "markdown": md,
        }
