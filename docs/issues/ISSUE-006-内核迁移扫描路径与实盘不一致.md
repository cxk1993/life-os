# ISSUE-006 · 内核迁移扫描路径与全部插件实盘目录不一致，builtin 迁移永不执行

> 编号顺延：docs/issues 现有 001–005。005 归 hermes（内核 api client 注入），勿混。

- **提出者**：Qoder CN（L2 真机验收线）
- **影响谁**：T14（`services/api/core/plugins/**` 领地，hermes）＋ Zcode（编排/部署）；**所有带表的 builtin 插件**（docs/todo/finance/notes/calendar/habits/review/agents/web…）
- **状态**：open
- **优先级**：blocker
- **日期**：2026-09-19

---

## 我遇到的现象

`services/api/core/plugins/migrations.py:24`：

```python
def _migration_dir(info): return info.directory / "api" / "migrations"
```

内核只扫 `modules/<id>/api/migrations/`；而**全部 builtin 插件的迁移实际放在 `modules/<id>/migrations/`**（如 `modules/docs/migrations/0001_init.py`、`0002_fts.py`）。两边永远对不上 ⇒ 插件升级/首装时其 SQL 迁移**一条都不会跑**。

复现（本机 dev 库，全新空库起后端后）：

1. 打开文档模块，右键新建文稿 → 输入正文 → 保存；
2. `PUT /api/v1/docs/nodes/{id}/content` → **500**，RFC7807 detail：`no such table: docs_node`；
3. 手工用 `importlib` 加载 `modules/docs/migrations/0001_init.py` 的 `upgrade(engine)` 执行后 → 同操作 **201/200 正常**，`/revisions`、FTS 搜索全部可用。

旁证（不是我第一个撞见，只是没人立卡）：
- `T13-report.md §3-4`：生产靠手工 `SQLModel.metadata.create_all` 绕过，并注明「迁移脚本扫描路径与实盘不一致，见既有 ISSUE」——但 `docs/issues/` 里始终没有这张卡；
- `T07-report.md:86`：「内核只扫 `modules/<id>/api/migrations/`，且 run_migrations 仅 third-party install 时执行；builtin 生产路径无自动建表 hook」。

## 为什么这会挡住我

任何**新环境**（干净库首启、灾备恢复、换机迁移）里所有带表模块一保存就 500；L2 验收每条数据链路都得先手工打补丁。手工 `create_all` 只建当前模型形状的表，**跳过 FTS5 虚拟表与后续 0002+ 增量**（docs 的 `docs_fts` trigrams 就在 0002），等于把插件作者写的迁移全部作废——这不是临时绕法，是静默数据层缺失。

## 我认为应该怎么改

给 T14 的两个可选口径（择一，或双跑）：

1. **扫描端兼容**：`_migration_dir()` 依次探测 `api/migrations/` 与 `migrations/`，取存在者；同时把 builtin 的 `run_migrations` 触发点从「仅 third-party install」扩到「启动时按 `_migration_history` 对账补跑」；
2. **实盘端统一**：把全部 `modules/<id>/migrations/` 移动到 `modules/<id>/api/migrations/`（机械移动，但涉及所有插件目录，需 Zcode 统一提交窗口）。

无论哪条，都要给 `deploy/` 首启流程加一条「所有已启用插件迁移全部落库」的断言检查（跑完后 `_migration_history` 覆盖当前版本清单）。

## 建议的验证方式

1. 删掉本地 dev 库 → 起后端（不手工干预）→ 浏览器登录 → 文档模块新建/保存/搜索全绿，无 500；
2. `SELECT name FROM sqlite_master WHERE name IN ('docs_node','docs_revision','docs_fts')` 三行齐；
3. 重启一次后端，确认迁移对账幂等（不重复执行、不报错）。
