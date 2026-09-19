"""日记业务逻辑：日期→路径换算 + get-or-create（幂等）+ 收件箱 + 归纳 + 时区。

★ 本卡**不建任何 diary_* 表**（薄壳）。
★ 「一天」= 路径 `日记/{yyyy}/{mm}/{yyyy-mm-dd}`（doc 节点）；定位永远走路径，保证幂等。
★ 数据读写经 **T15 的 HTTP API**（/api/v1/docs/...）——本 service 接收一个
  ``docs`` 适配器（默认用 httpx 请求 docs 模块），保持「跨插件只走 API + requires 声明」。
★ 时区：今天按 settings.tz（默认 Asia/Shanghai）切天，严禁用 UTC 切天。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol
from zoneinfo import ZoneInfo

from core.errors import ValidationError

DEFAULT_TZ = "Asia/Shanghai"
DIARY_ROOT_NAME = "日记"
INBOX_NAME = "收件箱"


class DocsAdapter(Protocol):
    """T15 docs API 的最小适配器（HTTP 层由 router 注入）。"""

    def tree(self) -> list[dict]: ...
    def create(
        self, parent_id: str | None, kind: str, name: str, meta: dict | None = None
    ) -> dict: ...
    def patch(self, node_id: str, body: dict) -> dict: ...


@dataclass
class DiaryService:
    """日记薄壳服务（纯逻辑，不持有 DB）。

    ``docs`` 是 T15 的 HTTP 适配器（默认由 router 用 httpx 构造）。
    ``tz`` 按 settings 注入（默认 Asia/Shanghai）。
    """

    docs: DocsAdapter
    tz: str = DEFAULT_TZ

    def __post_init__(self) -> None:
        self._tzinfo = ZoneInfo(self.tz)

    # ───────────────────────── 树工具 ─────────────────────────
    def _find_in_tree(self, nodes: list[dict], name: str, parent_id: str | None) -> dict | None:
        """在树里找 name + parent 匹配的节点（递归）。"""
        for n in nodes:
            if n.get("name") == name and n.get("parent_id") == parent_id:
                return n
            hit = self._find_in_tree(n.get("children") or [], name, parent_id)
            if hit:
                return hit
        return None

    # ───────────────────────── 根 / 收件箱（get-or-create 幂等） ─────────────────────────
    def ensure_diary_root(self, tree: list[dict]) -> str:
        """确保「日记」根存在，返回其 id。"""
        root = self._find_in_tree(tree, DIARY_ROOT_NAME, None)
        if root:
            return root["id"]
        return self.docs.create(None, "folder", DIARY_ROOT_NAME)["id"]

    def ensure_inbox(self, diary_root_id: str, tree: list[dict]) -> str:
        """确保「日记/收件箱」存在，返回其 id。"""
        inbox = self._find_in_tree(tree, INBOX_NAME, diary_root_id)
        if inbox:
            return inbox["id"]
        return self.docs.create(diary_root_id, "folder", INBOX_NAME)["id"]

    # ───────────────────────── 日期→路径 get-or-create（核心幂等） ─────────────────────────
    def get_or_create_entry(self, raw_date: str | None = None) -> dict:
        """定位某日日记：换算路径 → 找/建节点 → 返回 {node_id, path, exists, date}。

        幂等：重复调用同一天 → 同一确定路径 → 找到已存在节点，不新建。
        """
        d = self._parse_date(raw_date)
        yyyy = f"{d.year:04d}"
        mm = f"{d.month:02d}"
        node_name = d.isoformat()

        tree = self.docs.tree()
        root_id = self.ensure_diary_root(tree)

        year_node = self._find_in_tree(tree, yyyy, root_id)
        if not year_node:
            year_node = self.docs.create(root_id, "folder", yyyy)
        month_node = self._find_in_tree(tree, mm, year_node["id"])
        if not month_node:
            month_node = self.docs.create(year_node["id"], "folder", mm)
        day_node = self._find_in_tree(tree, node_name, month_node["id"])
        exists = day_node is not None
        if not day_node:
            day_node = self.docs.create(
                month_node["id"], "doc", node_name, meta={"diary_date": d.isoformat()}
            )

        return {
            "node_id": day_node["id"],
            "path": f"日记/{yyyy}/{mm}/{node_name}",
            "exists": exists,
            "date": d.isoformat(),
        }

    def today(self) -> date:
        """★ 按本地时区（settings.tz）切天，严禁用 UTC。"""
        return datetime.now(self._tzinfo).date()

    # ───────────────────────── 月历 / 收件箱 / 归纳 ─────────────────────────
    def month_days(self, year: int, month: int) -> list[str]:
        """该月已有日记的日期集合（YYYY-MM-DD）。"""
        yyyy = f"{year:04d}"
        mm = f"{month:02d}"
        tree = self.docs.tree()
        root_id = self.ensure_diary_root(tree)
        year_node = self._find_in_tree(tree, yyyy, root_id)
        if not year_node:
            return []
        month_node = self._find_in_tree(tree, mm, year_node["id"])
        if not month_node:
            return []
        days = []
        for child in month_node.get("children") or []:
            if child.get("kind") == "doc":
                name = child.get("name", "")
                if len(name) == 10 and name[4] == "-" and name[7] == "-":
                    days.append(name)
        return sorted(days)

    def inbox_items(self) -> list[dict]:
        """收件箱条目（按创建时间倒序）。"""
        tree = self.docs.tree()
        root_id = self.ensure_diary_root(tree)
        inbox = self._find_in_tree(tree, INBOX_NAME, root_id)
        if not inbox:
            return []
        items = []
        for child in inbox.get("children") or []:
            items.append(
                {
                    "id": child["id"],
                    "name": child["name"],
                    "created_at": child.get("created_at"),
                }
            )
        items.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        return items

    def capture(self) -> dict:
        """随手记：在收件箱下新建一条。name = 本地时间 YYYY-MM-DD-HHmm（重名 -2）。"""
        tree = self.docs.tree()
        root_id = self.ensure_diary_root(tree)
        inbox_id = self.ensure_inbox(root_id, tree)
        now = datetime.now(self._tzinfo)
        base_name = now.strftime("%Y-%m-%d-%H%M")
        name = base_name
        seq = 2
        while self._find_in_tree(tree, name, inbox_id):
            name = f"{base_name}-{seq}"
            seq += 1
        node = self.docs.create(inbox_id, "doc", name, meta={"source": "inbox"})
        return {"node_id": node["id"], "path": f"日记/收件箱/{name}", "name": name}

    def consolidate(self, node_id: str, target_date: str) -> dict:
        """归纳：收件箱条目移到目标日期所在月份下，同步 meta_json.diary_date。"""
        entry = self.get_or_create_entry(target_date)
        # 目标月份节点 = 路径 日记/{yyyy}/{mm}/{dd} 的上一级
        path_parts = entry["path"].split("/")
        if len(path_parts) < 4:
            raise ValidationError(f"路径解析失败：{entry['path']}")
        yyyy, mm = path_parts[1], path_parts[2]
        tree = self.docs.tree()
        root_id = self.ensure_diary_root(tree)
        year_node = self._find_in_tree(tree, yyyy, root_id)
        month_node = self._find_in_tree(tree, mm, year_node["id"]) if year_node else None
        if not month_node:
            raise ValidationError(f"目标月份节点不存在：{yyyy}/{mm}")

        self.docs.patch(node_id, {"parent_id": month_node["id"]})
        self.docs.patch(node_id, {"meta_json": {"source": "inbox", "diary_date": target_date}})
        return {
            "node_id": node_id,
            "target_date": target_date,
            "target_month_node": month_node["id"],
        }

    def _parse_date(self, raw: str | None) -> date:
        if raw is None:
            return self.today()
        try:
            return date.fromisoformat(raw)
        except ValueError as ex:
            raise ValidationError(f"date 格式应为 YYYY-MM-DD，收到 {raw!r}") from ex
