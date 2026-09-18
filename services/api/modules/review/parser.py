"""解析 Work-Review export-markdown 的 WR_BLOCK 块与中文时长。

★ 用 `<!-- WR_BLOCK_START:xxx -->` / `<!-- WR_BLOCK_END[:xxx] -->` 定位，
  **不要靠正则猜标题**。
★ 5 个块各自独立解析：缺谁不补谁，前端分别降级。
★ 空响应 → 各块空列表/空串，不抛异常。
★ 时长格式（真实数据）：`3小时13分52秒` / `41分13秒` / `29秒`。
"""
from __future__ import annotations

import re
from typing import Any

BLOCK_CATEGORY = "CATEGORY_TABLE"
BLOCK_APP = "APP_USAGE_TABLE"
BLOCK_DOMAIN = "DOMAIN_USAGE_TABLE"
BLOCK_HOURLY = "HOURLY_SUMMARY"
BLOCK_AI = "AI_ANALYSIS"
ALL_BLOCKS = (BLOCK_CATEGORY, BLOCK_APP, BLOCK_DOMAIN, BLOCK_HOURLY, BLOCK_AI)

_START_RE = re.compile(r"<!--\s*WR_BLOCK_START:([A-Z0-9_]+)\s*-->", re.IGNORECASE)
_END_RE = re.compile(r"<!--\s*WR_BLOCK_END(?::([A-Z0-9_]+))?\s*-->", re.IGNORECASE)

_HOUR_TOKEN_RE = re.compile(r"(\d+)\s*(?:小时|时|h)", re.IGNORECASE)
_MIN_TOKEN_RE = re.compile(r"(\d+)\s*(?:分|分钟|min)", re.IGNORECASE)
_SEC_TOKEN_RE = re.compile(r"(\d+)\s*(?:秒|s)", re.IGNORECASE)

_HEADER_HINTS = ("时长", "类别", "应用", "网站", "小时", "Duration", "Hour", "Name")
_HEADER_COL2 = ("时长", "时间", "Duration", "Time")
_NAME_HEADERS = ("类别", "应用", "网站", "小时", "名称", "Name")


def parse_duration(text: str | int | float | None) -> int:
    """中文/英文时长 → 秒。覆盖：
    - 3小时13分52秒 → 11632
    - 41分13秒      → 2473
    - 29秒          → 29
    - 空/非法       → 0
    """
    if text is None:
        return 0
    if isinstance(text, int | float):
        return max(0, int(text))
    s = str(text).strip()
    if not s:
        return 0
    hours = _HOUR_TOKEN_RE.search(s)
    minutes = _MIN_TOKEN_RE.search(s)
    seconds = _SEC_TOKEN_RE.search(s)
    total = 0
    if hours:
        total += int(hours.group(1)) * 3600
    if minutes:
        total += int(minutes.group(1)) * 60
    if seconds:
        total += int(seconds.group(1))
    if total == 0 and s.isdigit():
        return int(s)
    return total


def format_duration(total_seconds: int | float | None) -> str:
    """秒 → 中文时长（展示用）。"""
    sec = max(0, int(total_seconds or 0))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    parts: list[str] = []
    if h:
        parts.append(f"{h}小时")
    if m:
        parts.append(f"{m}分")
    if s or not parts:
        parts.append(f"{s}秒")
    return "".join(parts)


def extract_blocks(markdown: str | None) -> dict[str, str]:
    """按 WR_BLOCK 标记切块。缺的块不出现在结果里（各自独立）。"""
    text = markdown or ""
    out: dict[str, str] = {}
    for m in _START_RE.finditer(text):
        name = m.group(1).upper()
        start = m.end()
        end_m = _END_RE.search(text, start)
        body = text[start:].strip() if end_m is None else text[start : end_m.start()].strip()
        out[name] = body
    return out


def _parse_md_table(block: str | None) -> list[list[str]]:
    """从块内抽 Markdown 表格数据行（跳过表头与分隔行）。"""
    if not block:
        return []
    rows: list[list[str]] = []
    for line in (block or "").splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if not cells:
            continue
        if all(re.fullmatch(r":?-{2,}:?", c or "") for c in cells):
            continue
        if cells and re.fullmatch(r"[:\-\s]+", cells[0] or ""):
            continue
        joined = "".join(cells)
        if (
            not rows
            and any(k in joined for k in _HEADER_HINTS)
            and len(cells) >= 2
            and cells[1] in _HEADER_COL2
        ):
            continue
        rows.append(cells)
    return rows


def _rows_to_named(block: str | None) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for cells in _parse_md_table(block):
        if len(cells) < 1:
            continue
        name = cells[0]
        if not name or name in _NAME_HEADERS:
            continue
        dur_text = cells[1] if len(cells) > 1 else ""
        sec = parse_duration(dur_text)
        extra = cells[2] if len(cells) > 2 else ""
        item: dict[str, Any] = {
            "name": name,
            "seconds": sec,
            "duration_text": dur_text or format_duration(sec),
        }
        if extra:
            item["extra"] = extra
        items.append(item)
    return items


def _rows_to_hourly(block: str | None) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for cells in _parse_md_table(block):
        if len(cells) < 1:
            continue
        hour_raw = cells[0].strip()
        if not hour_raw or hour_raw in ("小时", "Hour"):
            continue
        try:
            hour = int(re.sub(r"[^\d]", "", hour_raw) or "-1")
        except ValueError:
            continue
        if hour < 0 or hour > 23:
            continue
        dur_text = cells[1] if len(cells) > 1 else ""
        sec = parse_duration(dur_text)
        items.append(
            {
                "hour": hour,
                "seconds": sec,
                "duration_text": dur_text or format_duration(sec),
            }
        )
    items.sort(key=lambda x: x["hour"])
    return items


def parse_export_markdown(markdown: str | None) -> dict[str, Any]:
    """完整解析 export-markdown → 结构化五块。空/缺块各自降级，不崩。"""
    blocks = extract_blocks(markdown)
    ai = blocks.get(BLOCK_AI, "").strip()
    return {
        "categories": _rows_to_named(blocks.get(BLOCK_CATEGORY)),
        "apps": _rows_to_named(blocks.get(BLOCK_APP)),
        "domains": _rows_to_named(blocks.get(BLOCK_DOMAIN)),
        "hourly": _rows_to_hourly(blocks.get(BLOCK_HOURLY)),
        "ai_analysis_md": ai,
        "blocks_found": sorted(blocks.keys()),
        "empty": not blocks and not (markdown or "").strip(),
    }


def _sec_from_item(item: dict[str, Any]) -> tuple[Any, int]:
    dur = item.get("duration_text") or item.get("duration") or item.get("time")
    sec = item.get("seconds")
    sec_i = parse_duration(dur) if sec is None else int(sec)
    return dur, sec_i


def normalize_report_payload(
    data: dict[str, Any] | None, markdown: str | None = None
) -> dict[str, Any]:
    """把 /v1/reports/{date} 的结构化 JSON 归一成内部形状。

    真实上游字段名可能不同：categories/category/CATEGORY_TABLE 等都尝试。
    markdown 解析结果作为回退补空。
    """
    data = data if isinstance(data, dict) else {}
    # 实测：GET /v1/reports/{date} 的 `content` 是带 WR_BLOCK 的 markdown 正文
    content_md = data.get("content") if isinstance(data.get("content"), str) else None
    if content_md and not markdown:
        markdown = content_md
    parsed_md = parse_export_markdown(markdown) if markdown else {
        "categories": [],
        "apps": [],
        "domains": [],
        "hourly": [],
        "ai_analysis_md": "",
        "empty": False,
    }

    def _as_rows(key_options: list[str], md_key: str) -> list[dict[str, Any]]:
        for key in key_options:
            val = data.get(key)
            if isinstance(val, list) and val:
                rows: list[dict[str, Any]] = []
                for item in val:
                    if not isinstance(item, dict):
                        continue
                    name = str(
                        item.get("name")
                        or item.get("app")
                        or item.get("category")
                        or item.get("host")
                        or item.get("domain")
                        or item.get("title")
                        or ""
                    ).strip()
                    if not name:
                        continue
                    dur, sec = _sec_from_item(item)
                    rows.append(
                        {
                            "name": name,
                            "seconds": sec,
                            "duration_text": str(dur or format_duration(sec)),
                        }
                    )
                if rows:
                    return rows
            if isinstance(val, dict):
                rows = []
                for name, sec in val.items():
                    try:
                        s = int(sec) if not isinstance(sec, str) else parse_duration(sec)
                    except (TypeError, ValueError):
                        s = parse_duration(str(sec))
                    rows.append(
                        {
                            "name": str(name),
                            "seconds": s,
                            "duration_text": format_duration(s),
                        }
                    )
                if rows:
                    return rows
        return list(parsed_md.get(md_key) or [])

    categories = _as_rows(
        ["categories", "category", "CATEGORY_TABLE", "category_json"], "categories"
    )
    apps = _as_rows(["apps", "app_usage", "APP_USAGE_TABLE", "applications"], "apps")
    domains = _as_rows(["domains", "domain_usage", "DOMAIN_USAGE_TABLE", "sites"], "domains")

    hourly: list[dict[str, Any]] = []
    for key in ("hourly", "hourly_json", "hourly_summaries", "HOURLY_SUMMARY"):
        val = data.get(key)
        if isinstance(val, list) and val:
            for item in val:
                if not isinstance(item, dict):
                    continue
                hour = item.get("hour")
                if hour is None:
                    hour = item.get("h")
                try:
                    h = int(hour) if hour is not None else -1
                except (TypeError, ValueError):
                    continue
                dur, sec = _sec_from_item(item)
                hourly.append(
                    {
                        "hour": h,
                        "seconds": sec,
                        "duration_text": str(dur or format_duration(sec)),
                    }
                )
            if hourly:
                break
    if not hourly:
        hourly = list(parsed_md.get("hourly") or [])

    ai = ""
    for key in ("ai_analysis_md", "ai_analysis", "AI_ANALYSIS", "analysis"):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            ai = val.strip()
            break
    if not ai:
        ai = str(parsed_md.get("ai_analysis_md") or "")

    empty_flag = bool(data.get("empty"))
    if not categories and not apps and not ai and not (markdown or "").strip():
        empty_flag = True
    if data.get("status") in ("empty", "no_data") or data.get("has_data") is False:
        empty_flag = True

    return {
        "categories": categories,
        "apps": apps,
        "domains": domains,
        "hourly": hourly,
        "ai_analysis_md": ai,
        "empty": empty_flag and not (categories or apps or domains or ai),
    }
