"""TX-PAT-01 · PAT 权限衰减与委派（切片 1：纯逻辑）。

scopes⊆ 校验 · 禁 '*' · TTL 窄化 · 级联吊销。
审计只记动作与 scope 集合，不落密钥。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class PatRecord:
    pat_id: str
    scopes: set[str]
    state: str = "active"  # active | narrowed | revoked
    last_used_at: datetime | None = None
    scope_history: list[tuple[datetime, str, str]] = field(default_factory=list)


def ensure_scopes_subset(requested: set[str], parent: set[str] | None) -> set[str]:
    if "*" in requested:
        raise ValueError("scope_denied:wildcard")
    if parent is None:
        return set(requested)
    if not requested <= parent:
        raise ValueError(f"scope_denied:not_subset:{sorted(requested - parent)}")
    return set(requested)


def call_allowed(pat: PatRecord, tool_scope: str) -> bool:
    if pat.state == "revoked":
        return False
    return tool_scope in pat.scopes


def narrow_ttl(
    pat: PatRecord, *, now: datetime, used: set[str], idle_days: int = 90
) -> PatRecord:
    if pat.state == "revoked" or pat.last_used_at is None:
        return pat
    if now - pat.last_used_at < timedelta(days=idle_days):
        return pat
    new = {s for s in pat.scopes if s in used}
    if new != pat.scopes:
        pat.scopes = new
        pat.state = "narrowed"
        pat.scope_history.append((now, "narrow_ttl", f"kept={sorted(new)}"))
    return pat


def revoke(
    pat: PatRecord, *, now: datetime, cascade_children: list[PatRecord] | None = None
) -> None:
    pat.state = "revoked"
    pat.scope_history.append((now, "revoked", ""))
    for c in cascade_children or []:
        if c.state != "revoked":
            c.state = "revoked"
            c.scope_history.append((now, "cascade_revoked", f"parent={pat.pat_id}"))
