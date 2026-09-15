"""Obsidian 任务行双向解析（T04 · 步骤 7）。

主人的真实语法（来自现有笔记）：
    - [ ] 每周备份 (@2026-10-01) 🔺 🔁 every week on Sunday

parse_todo_line()  解析出 done / text / due_at / priority / recur_rule / tags
to_todo_line()     还原回一行文本（规范化顺序：checkbox 文本 (@日期) 优先级 🔁 规则 #标签）

recur_rule 约定：
  - 能识别的重复规则 → RFC5545 RRULE（如 "every week on Sunday" → FREQ=WEEKLY;BYDAY=SU）
  - 识别不了的原样保留文本（宁可存原文，不静默猜）
  - to_todo_line() 做反向映射，保证常见规则往返一致
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

# 优先级（Obsidian Tasks 语法）：🔺高 🔼中 🔽低
PRIORITY_EMOJI = {"high": "🔺", "medium": "🔼", "low": "🔽"}
EMOJI_PRIORITY = {v: k for k, v in PRIORITY_EMOJI.items()}

_WEEKDAYS = {
    "monday": "MO", "tuesday": "TU", "wednesday": "WE", "thursday": "TH",
    "friday": "FR", "saturday": "SA", "sunday": "SU",
    "周一": "MO", "周二": "TU", "周三": "WE", "周四": "TH",
    "周五": "FR", "周六": "SA", "周日": "SU", "星期一": "MO", "星期日": "SU",
    "星期天": "SU",
}
_BYDAY_NAME = {v: k for k, v in _WEEKDAYS.items() if k.isascii()}

_LINE_RE = re.compile(r"^-\s+\[(?P<mark>[ xX])\]\s*(?P<body>.*)$")
_DUE_RE = re.compile(r"\(@(?P<date>\d{4}-\d{2}-\d{2})\)")
_TAG_RE = re.compile(r"#(?P<tag>[\w/\-]+)")


@dataclass
class TodoLine:
    """一行 Obsidian 任务的解析结果（todo_item 表的行内形态）。"""

    done: bool = False
    text: str = ""
    due_at: date | None = None
    priority: str | None = None  # high / medium / low
    recur_rule: str | None = None  # RRULE 或原文
    tags: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 重复规则 ⇄ RRULE
# ---------------------------------------------------------------------------
def rrule_from_text(rule: str) -> str | None:
    """"every week on Sunday" → "FREQ=WEEKLY;BYDAY=SU"；识别不了返回 None。"""
    s = rule.strip().lower().rstrip(".")
    m = re.fullmatch(r"every\s+(?:(\d+)\s+)?(day|week|month|year)s?(?:\s+on\s+(?P<day>\S+))?", s)
    if not m:
        return None
    n = m.group(1)
    freq_map = {"day": "DAILY", "week": "WEEKLY", "month": "MONTHLY", "year": "YEARLY"}
    freq = freq_map[m.group(2)]
    parts = [f"FREQ={freq}"]
    if n:
        parts.append(f"INTERVAL={n}")
    day = m.group("day")
    if day:
        byday = _WEEKDAYS.get(day)
        if byday is None:
            return None
        if freq != "WEEKLY":
            return None  # "every month on Monday" 之类，不做半个转换
        parts.append(f"BYDAY={byday}")
    return ";".join(parts)


def text_from_rrule(rrule: str) -> str | None:
    """RRULE → 人话；不是认识的形态返回 None（输出时原样保留）。"""
    parts = [p for p in rrule.strip().split(";") if p]
    kv: dict[str, str] = {}
    for p in parts:
        if "=" not in p:
            return None
        k, v = p.split("=", 1)
        kv[k.upper()] = v
    freq = kv.get("FREQ")
    if not freq:
        return None
    noun = {"DAILY": "day", "WEEKLY": "week", "MONTHLY": "month", "YEARLY": "year"}.get(freq)
    if noun is None:
        return None
    interval = kv.get("INTERVAL", "1")
    prefix = f"every {interval} {noun}s" if interval != "1" else f"every {noun}"
    byday = kv.get("BYDAY")
    if freq == "WEEKLY" and byday:
        name = _BYDAY_NAME.get(byday.upper())
        if name is None:
            return None
        return f"{prefix} on {name}"
    if byday:
        return None
    return prefix


# ---------------------------------------------------------------------------
# 解析 / 还原
# ---------------------------------------------------------------------------
def parse_todo_line(line: str) -> TodoLine:
    """一行 Obsidian 任务 → TodoLine。不是任务行（不以 `- [ ]` 开头）抛 ValueError。"""
    m = _LINE_RE.match(line.strip())
    if not m:
        raise ValueError(f"不是任务行（应为 `- [ ] …`）：{line[:60]!r}")
    todo = TodoLine(done=m.group("mark").lower() == "x")
    body = m.group("body")

    # 1) 截止日期 (@YYYY-MM-DD)
    due = _DUE_RE.search(body)
    if due:
        todo.due_at = date.fromisoformat(due.group("date"))
        body = body[: due.start()] + body[due.end():]

    # 2) 优先级 emoji（取第一个出现的）
    for i, ch in enumerate(body):
        if ch in EMOJI_PRIORITY:
            todo.priority = EMOJI_PRIORITY[ch]
            body = body[:i] + body[i + 1:]
            break

    # 3) 重复规则 🔁 <rule>
    recur = re.search(r"🔁\s*(?P<rule>.*)$", body)
    if recur:
        raw = recur.group("rule").strip()
        # 规则文本到行尾，但要先摘掉尾部 #标签
        tags = _TAG_RE.findall(raw)
        raw = _TAG_RE.sub("", raw).strip()
        todo.recur_rule = rrule_from_text(raw) or raw or None
        todo.tags.extend(tags)
        body = body[: recur.start()]

    # 4) 行内 #标签（不在重复规则里的）
    todo.tags.extend(_TAG_RE.findall(body))
    body = _TAG_RE.sub("", body)

    todo.text = re.sub(r"\s{2,}", " ", body).strip()
    return todo


def to_todo_line(todo: TodoLine) -> str:
    """TodoLine → 规范化的一行文本（与 parse 互逆）。"""
    mark = "x" if todo.done else " "
    parts = [f"- [{mark}] {todo.text}".rstrip()]
    if todo.due_at is not None:
        parts.append(f"(@{todo.due_at.isoformat()})")
    if todo.priority is not None:
        parts.append(PRIORITY_EMOJI[todo.priority])
    if todo.recur_rule:
        human = text_from_rrule(todo.recur_rule) or todo.recur_rule
        parts.append(f"🔁 {human}")
    parts.extend(f"#{t}" for t in todo.tags)
    return " ".join(parts)
