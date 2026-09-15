#!/usr/bin/env python
"""为内置插件生成可挂载骨架（T03 工具）。

用法（在 services/api 目录下）：
    python scripts/create_module.py <id> "<名称>"

生成 modules/<id>/ 下的 5 个文件：
    manifest.json  router.py  service.py  schema.py  README.md

生成的模块**直接可被内核发现并挂载**（manifest 字段满足内核运行期校验）。
注意：本脚本归 T03；第三方插件的 create_plugin.py 归 T14，不要混淆。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

if len(sys.argv) < 3:
    print("用法：python scripts/create_module.py <id> \"<名称>\"")
    raise SystemExit(2)

module_id = sys.argv[1].strip()
module_name = sys.argv[2].strip()
cap = module_id.capitalize()

# id 规则：小写英文/数字/连字符，以字母开头（与内核校验一致）
if not re.match(r"^[a-z][a-z0-9-]*$", module_id):
    print("❌ id 必须是小写英文/数字/连字符，且以字母开头")
    raise SystemExit(2)

_ROOT = Path(__file__).resolve().parents[1]
_target = _ROOT / "modules" / module_id
if _target.exists():
    print(f"❌ 已存在：{_target}")
    raise SystemExit(2)

_target.mkdir(parents=True, exist_ok=True)

manifest = {
    "id": module_id,
    "name": module_name,
    "version": "0.1.0",
    "kind": "builtin",
    "minKernel": "0.1.0",
    "kernelApi": "^1",
    "icon": "puzzle",
    "description": f"{module_name}（由 create_module.py 生成的内置插件骨架）",
    "author": "yunxi",
    "api": {
        "base": f"/api/v1/{module_id}",
        "openapi": f"/api/v1/{module_id}/openapi.json",
        "health": f"/api/v1/{module_id}/health",
    },
    "provides": [],
    "requires": [],
    "slots": [],
    "emits": [],
    "consumes": [],
    "permissions": ["db:own"],
    "lifecycle": {
        "onInstall": None,
        "onEnable": None,
        "onDisable": None,
        "onUninstall": None,
    },
}

router_py = f'''"""{module_name} 路由层（薄：只做参数校验和调用）。

★ 不要写 prefix=：内核按 manifest.api.base 自动挂 /api/v1/{module_id}。
★ 不要自己捕获异常：内核统一转 RFC7807。
★ 不需要自己处理 Idempotency-Key：内核中间件已做。
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session

from core.deps import get_current_user, get_db
from core.security import User
from .schema import {cap}Create, {cap}Out
from .service import {cap}Service

router = APIRouter()


@router.get("/health")
def health() -> dict[str, bool]:
    return {{"ok": True}}


@router.get("/items", response_model=list[{cap}Out])
def list_items(
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> list[dict]:
    return {cap}Service(db).list_items()


@router.post("/items", response_model={cap}Out, status_code=201)
def create_item(
    body: {cap}Create,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> dict:
    return {cap}Service(db).create(body)
'''

service_py = f'''"""{module_name} 业务逻辑层（厚：逻辑写这里）。

★ 单用户系统：业务表以插件 id 为前缀（{module_id}_xxx），跨插件只读对方 API。
★ 具体 Session 由 T04 通过 core.deps.set_engine 注入；这里只声明依赖。
★ 本骨架未建表，list 返回空、create 抛 NotImplementedError，挂载即可被发现。
   接 T04 数据库后，在 api/models.py 定义 {cap} 表并补实现。
"""
from __future__ import annotations

from typing import Any

from sqlmodel import Session

from .schema import {cap}Create, {cap}Out


class {cap}Service:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_items(self) -> list[dict]:
        return []  # 骨架：接 T04 后实现

    def create(self, body: {cap}Create) -> dict:
        raise NotImplementedError("业务实现待补充（接 T04 数据库后）")
'''

schema_py = f'''"""{module_name} 出入参。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class {cap}Create(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    note: Optional[str] = None


class {cap}Out(BaseModel):
    id: str
    title: str
    created_at: datetime
'''

readme = f"""# {module_name}（{module_id}）

内置插件骨架，由 `python scripts/create_module.py {module_id} "{module_name}"` 生成。

## 目录
- `manifest.json` 插件清单（内核发现依据）
- `router.py` 路由层（薄）
- `service.py` 业务层（厚）
- `schema.py` 出入参
- `api/models.py` 本插件表（需自建，表名以 `{module_id}_` 前缀）

## 注意
- 业务表由本插件在自己的 `api/migrations/` 里建，不碰 `services/api/db/**`。
- 路由前缀由内核按 manifest.api.base 自动添加，router 里不要写 prefix。
"""

files = {
    "manifest.json": None,  # 单独 json 写
    "__init__.py": "",
    "router.py": router_py,
    "service.py": service_py,
    "schema.py": schema_py,
    "README.md": readme,
}

# 写 manifest
(_target / "manifest.json").write_text(
    __import__("json").dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
for name, content in files.items():
    if name == "manifest.json":
        continue
    p = _target / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content or "", encoding="utf-8")

print(f"✅ 已生成插件骨架：{_target}")
print(f"   重启服务后将被自动发现并挂载到 /api/v1/{module_id}")
