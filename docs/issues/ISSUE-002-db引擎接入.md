# ISSUE-002 · db 引擎接入 main.py（T04 与 core 的最后一根线）

- **提出者**：T04（数据层）
- **影响谁**：`services/api/main.py`（ISSUE-001 判归 T03 维护）
- **状态**：**fixed**（编排者批准并代改，2026-09-15）
- **优先级**：normal（T04 交付的收尾接线）
- **日期**：2026-09-15

---

## 背景

T03 在 `core/deps.py` 预留了唯一注入点 `set_engine(工厂)`（不动 core、不 import db 的
干净设计）。T04 交付的 `db/engine.py` 提供 `init_engine()` 调用它。但**必须有人启动时
调一次 `init_engine()`**——而 main.py 属于 T03 的领地，T04 不许碰。

## 处理

按"需要改别人的东西 → 开卡"的规矩，本卡由编排者裁决并代改，改动共两行：

```python
from db.engine import init_engine
init_engine()
```

理由：
1. 这是 ISSUE-001 交接链的最后一环，方向早已由 T03 的 Protocol 设计确定；
2. 改动最小（两行 + 注释），不触碰 create_app 内部；
3. `data/lifos.db` 不存在时由 `db/engine.py` 自动建目录建库，无静默回退。

## 对后续卡的影响

- T14 / 各插件：`Depends(get_db)` 从现在起返回真实 SQLite 会话。
- T13：部署时确认容器内 `data/` 卷挂载（备份脚本同路径）。
