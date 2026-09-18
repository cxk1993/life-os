# ISSUE-004 · review_daily 的 raw_md / review_note 未登记进数据字典

- **提出者**：T09（复盘插件）
- **影响谁**：T04（数据字典维护）
- **状态**：open
- **优先级**：low
- **日期**：2026-09-18

---

## 我遇到的现象

`contracts/data-dictionary.md` 已有表名行：

```text
| review_daily | review | (date) 唯一，日报按天取 |
```

T09 实现时在插件侧补了列与新表，但**未改**数据字典（那是 T04 领地）：

1. `review_daily` 新增列（任务卡映射要求）：
   - `raw_md` TEXT —— export-markdown 原文
   - `raw_path` TEXT —— 值形如 `work-review:<date>`，是**来源标识**，不是文件路径
   - `is_empty` / `synced_at` —— 空日标记与同步时间
2. 批注表 `review_note`（date / content_md）由 review 插件 models 自建，表名前缀 `review_`，字典未登记。

## 为什么这会挡住我

不挡开发，但契约字典与真实表结构不一致，后续 T17/概览订阅方会误读 `raw_path` 为磁盘路径。

## 我认为应该怎么改

请 T04 负责人在 `review_daily` 行补充列说明，并增加 `review_note` 行：

```text
| review_daily | review | (date) 唯一；raw_path 为来源标识 work-review:<date>，非路径；含 raw_md/is_empty/synced_at |
| review_note | review | (date) 主人批注，与机器日报分表 |
```

## 建议的验证方式

字典更新后，插件 README 与 T09 报告中的字段说明应与字典一致；`modules/review/models.py` 无需改动。
