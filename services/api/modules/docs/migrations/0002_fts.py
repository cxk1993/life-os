"""插件迁移 0002：建 docs_fts（FTS5 全文索引虚拟表）+ 历史数据回填。

★ 只增不改：已执行过的迁移文件不许再动。
★ ★ 中文友好：**trigram**，零新依赖，不引入搜索引擎。
  （任务卡原文写 bigram；但实测本环境 SQLite 3.45.1 标准发行版**不带 bigram**，
  报 no such tokenizer。trigram 是 FTS5 内建、SQLite 3.34+ 可用、对中文子串
  同样友好 —— 故按「先探再答」改用 trigram。详见 T15-report。）
★ FTS 由 service 层在增改删时同步维护；本迁移只负责建表和回填存量。
"""
from __future__ import annotations

from typing import Any


def upgrade(engine: Any) -> None:
    with engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(
              node_id UNINDEXED,
              title,
              body,
              tokenize = 'trigram'
            )
            """
        )
        # 回填存量：软删的节点也建索引，但查询时 JOIN 过滤 deleted_at IS NULL
        conn.exec_driver_sql(
            """
            INSERT INTO docs_fts(node_id, title, body)
            SELECT n.id, n.name, c.body
            FROM docs_node n
            LEFT JOIN docs_content c ON c.node_id = n.id
            WHERE n.kind = 'doc'
            """
        )


def downgrade(engine: Any) -> None:
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE IF EXISTS docs_fts")
