"""用 contracts/plugin.schema.json 对 manifest 做强校验（总纲 §1.3.1）。

★ 这是"一切皆插件"的机器守门人之一：校验失败必须精确到
  「哪个插件 · 哪个字段 · 期望什么 · 实际什么」，不许静默跳过。

实现说明：不引入 jsonschema 依赖，自实现一个覆盖本项目用到的 JSON Schema
关键字子集（type / required / enum / pattern / minLength / minimum /
items / properties / additionalProperties / 可空联合），足够支撑契约校验，
且错误信息完全可控。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.errors import ManifestError

_SCHEMA_PATH = (
    Path(__file__).resolve().parents[4] / "contracts" / "plugin.schema.json"
)

_SCHEMA: dict[str, Any] = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _match_type(value: Any, typ: Any) -> bool:
    """支持单类型与 [a, b, ...] 联合（本项目仅用于 可空联合 [string, null]）。"""
    if isinstance(typ, list):
        return any(_match_type(value, t) for t in typ)
    name = _type_name(value)
    if typ == "integer":
        # JSON 里整数是 int；bool 不是 integer
        return isinstance(value, int) and not isinstance(value, bool)
    if typ == "number":
        return isinstance(value, int | float) and not isinstance(value, bool)
    if typ == "boolean":
        return name == "boolean"
    if typ == "string":
        return name == "string"
    if typ == "array":
        return name == "array"
    if typ == "object":
        return name == "object"
    if typ == "null":
        return value is None
    return name == typ


def _validate_node(
    value: Any,
    schema: dict[str, Any],
    path: str,
    errors: list[str],
) -> None:
    typ = schema.get("type")
    if typ is not None and not _match_type(value, typ):
        errors.append(
            f"{path or '<root>'}: 期望类型 {typ}，实际为 {_type_name(value)}"
        )
        # 类型都不对，后续细项校验无意义
        return

    if isinstance(value, dict):
        required = schema.get("required", [])
        for field in required:
            if field not in value:
                errors.append(f"{path}.{field}: 缺少必填字段（契约要求：{field}）")
        props = schema.get("properties", {})
        for field, sub in props.items():
            if field in value:
                _validate_node(value[field], sub, f"{path}.{field}", errors)
        addl = schema.get("additionalProperties", True)
        if addl is False:
            for field in value:
                if field not in props:
                    errors.append(
                        f"{path}.{field}: 未知字段（契约不允许，请删除或走 RFC 流程）"
                    )

    elif isinstance(value, list):
        items_schema = schema.get("items")
        if items_schema is not None:
            for idx, item in enumerate(value):
                _validate_node(item, items_schema, f"{path}[{idx}]", errors)

    if "enum" in schema and value not in schema["enum"]:
        errors.append(
            f"{path}: 取值 {value!r} 不在允许集合 {schema['enum']} 内"
        )
    if "pattern" in schema:
        import re

        if not re.match(schema["pattern"], str(value)):
            errors.append(
                f"{path}: 值 {value!r} 不匹配格式 {schema['pattern']}"
            )
    if "minLength" in schema and isinstance(value, str) and len(value) < schema["minLength"]:
        errors.append(
            f"{path}: 字符串长度至少为 {schema['minLength']}，实际为 {len(value)}"
        )
    if "minimum" in schema and isinstance(value, int | float) and value < schema["minimum"]:
        errors.append(
            f"{path}: 数值至少为 {schema['minimum']}，实际为 {value}"
        )


def validate_manifest(raw: dict[str, Any]) -> dict[str, Any]:
    """校验 manifest 字典。通过则返回原字典；失败抛 ManifestError（精确到字段）。"""
    errors: list[str] = []
    _validate_node(raw, _SCHEMA, "manifest", errors)
    if errors:
        raise ManifestError(
            "manifest 校验失败（对照 contracts/plugin.schema.json）：\n  - "
            + "\n  - ".join(errors)
        )
    return raw


def validate_manifest_text(text: str, source: str = "manifest.json") -> dict[str, Any]:
    """从文本校验（顺便检查 JSON 是否合法）。"""
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ManifestError(f"{source} 不是合法 JSON：{exc}") from exc
    if not isinstance(raw, dict):
        raise ManifestError(f"{source} 根必须是对象")
    return validate_manifest(raw)
