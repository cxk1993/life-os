# 侧栏自定义容器（插件 id：`sidebar`）

由 `scripts/create_plugin.py` 生成。**请先读 `docs/adr/0002-插件协议.md`。**

| 项 | 值 |
|:--|:--|
| id | `sidebar` |
| kind | `builtin` |
| API 前缀 | `/api/v1/sidebar` |
| 表名前缀 | `sidebar_` |
| 迁移目录 | `api/migrations/` |

## 改这个插件时不许做的事

1. 不许 import 别的插件 —— 走事件总线 / 对方公开 API / 扩展点
2. 不许 join 别人的表 —— 要数据就调对方的 API，并在 manifest.requires 里声明
3. 不许自己写登录 —— 内核统一注入 `Authorization: Bearer <jwt>`
4. 不许写死颜色 —— 只用设计令牌（`var(--accent)` 之类）
5. 不许改 `kernel/` 或 `core/` —— 那是框架的 bug，去 `docs/issues/` 写卡
