# ISSUE-007 设计与验收草案 · todo 订阅 health.care.requested

> **署名**：Xiaomi MiMo（小云昔）｜ **时间**：2026-09-20 凌晨
> **性质**：详细设计草案 · 供总监派工后直接实施
> **领地**：todo 模块（`services/api/modules/todo/**`）—— **health 侧不改**

---

## 1. 事件契约（health 侧已实现，勿改）

```text
topic: health.care.requested
payload: {
  record_id: str,
  kind: str,
  title: str,
  suggest_due: str|null,     # ISO date
  source: "health",
  idempotency_key: "health-followup:{record_id}:{due|none}"
}
```

## 2. todo 侧实现方案

### 2.1 订阅位置

在 todo 模块的服务层（或独立 handler）订阅事件：

```python
# services/api/modules/todo/service.py 或 handlers.py
from core.events import event_bus

def _handle_health_care(event: dict) -> None:
    payload = event.get("payload", {})
    key = payload.get("idempotency_key")
    if not key:
        return
    # 幂等：查是否已有该 key 对应的 todo
    ...
```

### 2.2 字段映射

| health payload | todo 字段 | 说明 |
|:--|:--|:--|
| `title` | `title` | 前缀「跟进：」或直接用原 title |
| `suggest_due` | `due_at` | ISO date；空则 +3 天（Asia/Shanghai） |
| `source` | `source` / `tags` | 标记来源 `health` |
| `idempotency_key` | `meta_json.idempotency_key` | 幂等去重键 |
| `record_id` | `meta_json.health_record_id` | 可回链 |

### 2.3 幂等去重

- 创建 todo 前查 `meta_json` 里是否已有相同 `idempotency_key`；
- 有则**跳过**（或更新 due，待总监定）；
- 无则创建。

### 2.4 事件订阅注册

在 todo 模块启动时注册：

```python
# modules/todo/__init__.py 或 startup
event_bus.subscribe("health.care.requested", _handle_health_care)
```

（需确认 event_bus 的订阅 API —— 若是 SSE 订阅模式，可能需要不同机制。）

## 3. 验收测试

| 用例 | 断言 |
|:--|:--|
| 健康记录 `followup_needed=true` | todo 出现一条，title 含 health title |
| 相同 `idempotency_key` 二次事件 | 不新增第二条 todo |
| `suggest_due` 为空 | due_at = 今天 +3 天 |
| `suggest_due` 有值 | due_at = 该日期 |
| 事件 payload 格式 | todo 读取后字段映射正确 |

## 4. 实施步骤（派工后）

1. 读 todo 模块结构（service / models / events）
2. 实现 `_handle_health_care`
3. 注册订阅
4. 写测试 `tests/test_todo_health_linkage.py`
5. 跑全部 todo 测试 + health 测试（确认无回归）
6. 报告 + 完工帖 @Zcode

## 5. 领地声明

```
✅ 可改：services/api/modules/todo/**
✅ 可改：services/api/tests/test_todo*.py
❌ 不改：services/api/modules/health/**（已交付）
❌ 不改：core/events.py
```

---

**状态**：设计草案已交，等总监派工。
**预计工时**：1-2 小时。
