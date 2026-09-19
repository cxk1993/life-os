# 人格体系（插件 id：`persona`）

> T16 · 人格体系 —— 文档树内核（T15）的**薄壳入口**。
> ★ 不建表、不认识「人格」概念。所有数据读写走 T15 的 `docs.node.*` / `docs.search`。

## 设计原则（留白）

「人格体系」四个字只出现在**窗口标题与文案**里；
代码与表结构里**不存在任何人格专有实体**。

价值观 / 性格 / 情绪 / 标签 / 评分 / 头像 / 关系……全部进 T15 的 `docs_node.meta_json`，
或由前端纯展示。**新增任何人格要素都不需要数据库迁移。**

## 边界

- `requires: ["docs.node.read", "docs.node.write", "docs.search"]`（manifest 已声明）
- 不 import T15 的 Python 模块、不 join docs_* 表（ADR-0002）
- 复用 T15 导出的 `DocsTree` / `DocsViewer` / `MarkdownView` 组件，不重写

## API

仅 `/health`（薄壳无领域接口）。
