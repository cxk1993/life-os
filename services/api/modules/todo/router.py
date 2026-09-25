"""待办与周期清单路由（薄：只做参数校验 + 调 service + 发事件）。

HTTP 契约（全项目统一，不许自创）：
  成功 → 直接返回资源 JSON（200/201）
  失败 → 由内核统一转成 RFC7807 application/problem+json

★ 前缀由内核按 manifest.api.base 自动加，这里**不要写 prefix=**。
★ 不自己捕获异常包成自定义格式，内核统一处理。
★ 事件总线：写操作在 service 层 publish 到 event_bus，内核 SSE
  （/api/v1/events/subscribe）自动下推，无需在此手动发。
★ 幂等（Idempotency-Key）由内核 IdempotencyMiddleware 自动处理，这里不重复做。
★ 内部一律用包路径导入（from modules.todo.xxx import ...）。
★ 路径参数用 Annotated[str, FPath(...)]（不是 = FPath(...)）：
  后者是「带默认值的参数」，会逼后面的 body 也必须给默认值。
★ 本文件**不要**加 `from __future__ import annotations`：
  它会把 `-> None` 变成字符串 "None" → get_type_hints 得到 NoneType（truthy）
  → FastAPI 认为 204 带了响应体 → 整个后端起不来。
"""
import json
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from fastapi import Path as FPath
from sqlmodel import Session

from core.deps import get_current_user, get_db
from core.errors import NotFoundError, ValidationError
from core.security import User

from . import health_link as _health_link  # noqa: E402,F401  ISSUE-007
from .schema import (
    ExportIn,
    ExportOut,
    ImportIn,
    ImportOut,
    SummaryOut,
    TodoCreate,
    TodoItemOut,
    TodoListOut,
    TodoUpdate,
    ToggleOut,
)
from .service import TodoService

router = APIRouter()

_MANIFEST_PATH = Path(__file__).resolve().parent / "manifest.json"
with _MANIFEST_PATH.open(encoding="utf-8") as _f:
    _MANIFEST = json.load(_f)

# ★ 依赖别名**只做类型**，不要把 Depends 塞进 Annotated。
DbDep = Session
UserDep = User


@router.get("/health")
def health() -> dict[str, bool]:
    """每个插件都必须有 health —— 内核据此判断"该能力是否可用"。"""
    return {"ok": True}


@router.get("/manifest")
def manifest() -> dict:
    """模块清单（前端 / AI 发现能力用）。"""
    return _MANIFEST


@router.get("/items", response_model=TodoListOut)
def list_items(
    status: str | None = Query(None, description="done | todo | all（默认 all）"),
    due_before: str | None = Query(None, description="截止时间上界，带时区 ISO8601"),
    due_after: str | None = Query(None, description="截止时间下界，带时区 ISO8601"),
    tag: str | None = Query(None, description="按标签过滤"),
    source: str | None = Query(None, description="按来源文件路径过滤"),
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = Query(None, description="分页游标（opaque）"),
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    items, next_cursor = TodoService(db).list_items(
        status=status, due_before=due_before, due_after=due_after,
        tag=tag, source=source, limit=limit, cursor=cursor,
    )
    return {"items": items, "next_cursor": next_cursor}


@router.post("/items", response_model=TodoItemOut, status_code=status.HTTP_201_CREATED)
def create_item(
    body: TodoCreate,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    # 事件在 service 层发布（todo.item.created）
    return TodoService(db).create(body)


@router.get("/items/{item_id}", response_model=TodoItemOut)
def get_item(
    item_id: Annotated[str, FPath(description="待办 id")],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    return TodoService(db).get(item_id)


@router.patch("/items/{item_id}", response_model=TodoItemOut)
def update_item(
    item_id: Annotated[str, FPath(description="待办 id")],
    body: TodoUpdate,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    return TodoService(db).update(item_id, body)


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(
    item_id: Annotated[str, FPath(description="待办 id")],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> None:
    TodoService(db).delete(item_id)


@router.post("/items/{item_id}/toggle", response_model=ToggleOut)
def toggle_item(
    item_id: Annotated[str, FPath(description="待办 id")],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> ToggleOut:
    # 完成 → 写 done_at；若是周期任务 → 生成下一条实例并保留历史。
    # 事件在 service 层发布（todo.item.completed / todo.item.updated / todo.item.created）。
    return TodoService(db).toggle(item_id)


@router.post("/import", response_model=ImportOut)
def import_markdown(
    body: ImportIn,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """从 Obsidian 文件批量导入，保留原行位置（记录 source_path + 行号）。

    两种来源二选一：content（直接给 markdown 文本）或 path（本机文件路径）。
    """
    if body.content is not None:
        content, source_path = body.content, body.path
    elif body.path is not None:
        p = Path(body.path)
        if not p.is_file():
            raise NotFoundError(f"导入源文件不存在：{body.path}")
        content, source_path = p.read_text(encoding="utf-8"), body.path
    else:
        raise ValidationError("import 需要 content 或 path 至少一个")
    imported, lines, items = TodoService(db).import_markdown(content, source_path)
    return {"imported": imported, "lines": lines, "items": items}


@router.post("/export", response_model=ExportOut)
def export_markdown(
    body: ExportIn | None = None,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> ExportOut:
    """导出回 markdown 文本（供前端 diff 预览，v0.1 不自动写回 Obsidian）。"""
    body = body or ExportIn()
    markdown = TodoService(db).export_markdown(status=body.status, tag=body.tag)
    return ExportOut(markdown=markdown)


@router.get("/summary", response_model=SummaryOut)
def summary(
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> SummaryOut:
    """概览统计：今日待办 / 逾期 / 本周完成。"""
    return TodoService(db).summary()


@router.get("/today-summary")
def today_summary(
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    """U2 今日摘要（today-summary 规范 v1：{title, items<=5:[{text,state,count?}], link}）。

    内核 BFF /api/v1/summary/today 的转发目标（派工令 62）。
    """
    return TodoService(db).today_summary()


# ═══════ ★ TX-TODO-REMIND-01（主人 2026-09-25「做」）：待办到期提醒 ═══════
# 链路：due_scheduler 扫到期 → publish("todo.item.due") → push.link → web push
@router.post("/due/tick")
def post_due_tick(
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict:
    """手动触发一轮待办到期扫描（验收/排障用；不依赖定时是否开启）。"""
    from .due_scheduler import run_due_tick

    return {"ok": True, "count": run_due_tick(db)}


@router.get("/due/scheduler")
def get_due_scheduler_status(
    _user: UserDep = Depends(get_current_user),
) -> dict:
    """待办到期提醒调度状态（enabled/running/poll/window）。"""
    from .due_scheduler import scheduler_status

    return scheduler_status()


try:
    from .due_scheduler import start_scheduler as _start_due

    _start_due()
except Exception as _due_exc:  # noqa: BLE001
    import logging

    logging.getLogger("todo.due").warning("待办到期提醒调度启动失败: %s", _due_exc)
