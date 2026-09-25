"""笔记路由（薄：参数校验 + 调 service）。

HTTP 契约：成功直接返回资源 JSON；失败由内核转 RFC7807。
★ 前缀由内核按 manifest.api.base 自动加，这里不要写 prefix=。
★ 路径参数用 Annotated[str, FPath(...)]；本文件不要加 future import。
"""
import json
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status, Response
from fastapi import Path as FPath
from sqlmodel import Session

from core.deps import get_current_user, get_db
from core.security import User

from .schema import LibCreate, LibOut, NoteCreate, NoteDetail, NoteUpdate, NoteTree, SearchOut, SyncResult
from .service import NotesService

router = APIRouter()

_MANIFEST_PATH = Path(__file__).resolve().parent / "manifest.json"
with _MANIFEST_PATH.open(encoding="utf-8") as _f:
    _MANIFEST = json.load(_f)

DbDep = Session
UserDep = User


@router.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@router.get("/manifest")
def manifest() -> dict:
    return _MANIFEST


@router.get("/libs", response_model=list[LibOut])
def list_libs(
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> list[dict[str, Any]]:
    return NotesService(db).list_libs()


@router.get("/libs/{lib_id}/tree", response_model=NoteTree)
def get_tree(
    lib_id: Annotated[str, FPath()],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    return NotesService(db).get_tree(lib_id)


@router.post("/libs", response_model=LibOut, status_code=status.HTTP_201_CREATED)
def upsert_lib(
    body: LibCreate,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    return NotesService(db).upsert_lib(body)


@router.post("/libs/{lib_id}/sync", response_model=SyncResult)
def sync_lib(
    lib_id: Annotated[str, FPath()],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    return NotesService(db).sync_lib(lib_id)


@router.post("/sync", response_model=list[SyncResult])
def sync_all(
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> list[dict[str, Any]]:
    return NotesService(db).sync_all()


@router.get("/search", response_model=SearchOut)
def search(
    q: str | None = Query(None, description="标题 / 摘要模糊搜索"),
    lib_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    return NotesService(db).search(q=q, lib_id=lib_id, limit=limit)


@router.get("/notes/{note_id}", response_model=NoteDetail)
def get_note(
    note_id: Annotated[str, FPath()],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    return NotesService(db).get_note(note_id)

@router.get("/attachment")
def get_attachment(
    lib: str = Query("attach", description="库 key（默认 attach = obsidian 附件库）"),
    path: str = Query(..., description="附件相对路径，如 xxx.png"),
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> Response:
    """★ 读二进制附件（图片等）· astrbot 下场 · 主人⑤「ob 附件、图片插入要能正常展示」。

    前端 MdView 把 `![](xxx.png)` 的 src 重写为本端点（同源），由本端点经桥取回原始字节。
    安全：桥侧 safe_resolve 双守卫（路径穿越 + 越界）；本端点只做鉴权 + 透传。
    """
    data, mime = NotesService(db).get_attachment(lib, path)
    return Response(content=data, media_type=mime, headers={"Cache-Control": "private, max-age=300"})


@router.post("/libs/{lib_id}/notes", response_model=NoteDetail, status_code=status.HTTP_201_CREATED)
def create_note(
    lib_id: Annotated[str, FPath()],
    body: NoteCreate,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    return NotesService(db).create_note(lib_id, body)


@router.put("/notes/{note_id}", response_model=NoteDetail)
def update_note(
    note_id: Annotated[str, FPath()],
    body: NoteUpdate,
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> dict[str, Any]:
    return NotesService(db).update_note(note_id, body)


@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(
    note_id: Annotated[str, FPath()],
    db: DbDep = Depends(get_db),
    _user: UserDep = Depends(get_current_user),
) -> None:
    NotesService(db).delete_note(note_id)
