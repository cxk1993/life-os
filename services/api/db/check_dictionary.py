"""数据字典自动比对（T04 · 步骤 13）：python -m db.check_dictionary

比对 contracts/data-dictionary.md「内核表」一节与 db/models 的 SQLModel 元数据：
  - 表集合一致（模型有而字典没有 → 漏登记；反之 → 幽灵行）
  - 字段集合一致
  - 类型语义一致（str/int/bool/datetime/text 粗粒度映射）
  - 主键一致

输出「一致」或逐条差异；有差异退出码 1（可挂进 make lint / CI）。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from sqlalchemy import String, Text
from sqlalchemy.types import Boolean, DateTime, Integer, TypeDecorator

from db.base import Base

_DICT_PATH = Path(__file__).resolve().parents[3] / "contracts" / "data-dictionary.md"

_ROW_RE = re.compile(r"^\|\s*([a-z_]+)\s*\|\s*([a-z_]+)\s*\|\s*([a-z()\d ]+?)\s*\|")

# 字典类型词 → _sa_category 的返回值
_TYPE_OF = {
    "str": ("str",), "text": ("text",), "int": ("int",),
    "bool": ("bool",), "datetime": ("datetime",),
}


def _sa_category(col: Any) -> str:
    """把 SQLAlchemy 列类型粗归类为字典类型词。

    TypeDecorator（SQLModel 的 AutoString、本项目的 UTCDateTime）先拆出 impl
    再归类，否则全部落进 unknown。
    """
    t = col.type
    if isinstance(t, TypeDecorator):
        t = t.impl  # 包装类的底层类型（类对象）
    if isinstance(t, Text):
        return "text"
    if isinstance(t, String):
        return "str"
    if isinstance(t, Boolean):
        return "bool"
    if isinstance(t, DateTime):
        return "datetime"
    if isinstance(t, Integer):
        return "int"
    return "unknown"


def parse_dictionary(path: Path | None = None) -> dict[str, dict[str, dict[str, str | bool]]]:
    """解析内核表一节 → {表: {字段: {类型, 主键}}}。

    值的类型是 `str | bool`：`type` 是字符串、`pk` 是布尔（原标注写成 `dict[str, str]`，
    与写入的 `"pk": bool` 不符，mypy 在下游比较处报 dict-item / comparison-overlap）。
    """
    src = (path or _DICT_PATH).read_text(encoding="utf-8")
    # 只取「内核表」一节，业务表登记不参与逐字段比对
    section = src.split("## 内核表", 1)[1].split("## 业务表", 1)[0]
    tables: dict[str, dict[str, dict[str, str | bool]]] = {}
    for line in section.splitlines():
        m = _ROW_RE.match(line)
        if not m:
            continue
        table, fld, typ = m.group(1), m.group(2), m.group(3).strip()
        tables.setdefault(table, {})[fld] = {"type": typ, "pk": "pk" in typ.split()}
    return tables


def compare(path: Path | None = None) -> tuple[bool, list[str]]:
    """（是否一致, 差异列表）。模型以 Base.metadata 为准绳，双向核对。"""
    from db import models  # noqa: F401  导入即注册内核表

    dict_tables = parse_dictionary(path)
    diffs: list[str] = []

    meta_tables = set(Base.metadata.tables)
    dict_table_names = set(dict_tables)
    for t in sorted(meta_tables - dict_table_names):
        diffs.append(f"模型有而字典未登记：{t}")
    for t in sorted(dict_table_names - meta_tables):
        diffs.append(f"字典有而模型不存在：{t}")

    for t in sorted(meta_tables & dict_table_names):
        model_cols = Base.metadata.tables[t].columns
        dict_cols = dict_tables[t]
        for c in model_cols:
            if c.name not in dict_cols:
                diffs.append(f"{t}.{c.name}：模型有而字典未登记")
                continue
            entry = dict_cols[c.name]
            if bool(c.primary_key) != entry["pk"]:
                diffs.append(f"{t}.{c.name}：主键标记不一致（模型={c.primary_key}）")
            cat = _sa_category(c)
            raw_type = entry["type"]
            expected = (raw_type if isinstance(raw_type, str) else "").split("(")[0]
            if expected in _TYPE_OF and cat not in _TYPE_OF[expected]:
                diffs.append(f"{t}.{c.name}：类型不一致（字典={entry['type']}，模型={cat}）")
        for f in sorted(set(dict_cols) - {c.name for c in model_cols}):
            diffs.append(f"{t}.{f}：字典有而模型不存在")

    return (not diffs), diffs


def main() -> int:
    ok, diffs = compare()
    if ok:
        print("一致：contracts/data-dictionary.md 与 db/models 逐字段一致")
        return 0
    print("不一致：发现以下差异：")
    for d in diffs:
        print(f"  - {d}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
