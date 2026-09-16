"""插件设置读写与校验（总纲 §1.3 / 验收 #8）。

插件若声明了 settingsSchema（一个 JSON Schema 文件，路径相对插件根），
则其设置必须经该 Schema 校验后才能落库（plugin_setting 表）。
写错类型 / 缺字段 / 越界 → 明确拒绝，不许静默存进去。
"""
from __future__ import annotations

import json
from typing import Any

from sqlmodel import Session, select

from core.errors import ValidationError
from core.plugins.validate import _validate_node
from db.models.system import PluginSetting

_SCHEMA_CACHE: dict[str, dict[str, Any]] = {}


def _load_schema(info: Any) -> dict[str, Any] | None:
    rel = info.manifest.get("settingsSchema")
    if not rel:
        return None
    path = info.directory / rel
    if not path.is_file():
        return None
    if path.as_posix() in _SCHEMA_CACHE:
        return _SCHEMA_CACHE[path.as_posix()]
    schema = json.loads(path.read_text(encoding="utf-8"))
    _SCHEMA_CACHE[path.as_posix()] = schema
    return schema


def validate_settings(info: Any, settings: dict[str, Any]) -> dict[str, Any]:
    """按插件的 settingsSchema 校验；无 schema 则原样通过。"""
    if not isinstance(settings, dict):
        raise ValidationError("设置必须是对象")
    schema = _load_schema(info)
    if schema is None:
        return settings
    errors: list[str] = []
    _validate_node(settings, schema, "settings", errors)
    if errors:
        raise ValidationError(
            f"插件「{info.id}」设置校验失败：\n  - " + "\n  - ".join(errors)
        )
    return settings


def read_settings(session: Session, plugin_id: str) -> dict[str, Any]:
    """读取插件全部设置 → {key: value_json 解析后的值}。"""
    rows = session.exec(
        select(PluginSetting).where(PluginSetting.plugin_id == plugin_id)
    ).all()
    out: dict[str, Any] = {}
    for r in rows:
        try:
            out[r.key] = json.loads(r.value_json)
        except json.JSONDecodeError:
            out[r.key] = r.value_json
    return out


def write_settings(
    session: Session,
    info: Any,
    plugin_id: str,
    settings: dict[str, Any],
) -> dict[str, Any]:
    """校验后写入（逐 key upsert）。返回写入后的完整设置。"""
    validate_settings(info, settings)
    for key, value in settings.items():
        value_json = json.dumps(value, ensure_ascii=False)
        existing = session.exec(
            select(PluginSetting).where(
                PluginSetting.plugin_id == plugin_id, PluginSetting.key == key
            )
        ).first()
        if existing is None:
            session.add(
                PluginSetting(plugin_id=plugin_id, key=key, value_json=value_json)
            )
        else:
            existing.value_json = value_json
    session.commit()
    return read_settings(session, plugin_id)
