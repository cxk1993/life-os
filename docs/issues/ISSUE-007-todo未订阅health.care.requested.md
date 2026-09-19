# ISSUE-007 · todo 未订阅 health.care.requested —— 插件联动消费方缺口

- **提出者**：Xiaomi MiMo（T21 实装，2026-09-20）
- **影响谁**：T06 待办（`services/api/modules/todo/**`，领地所有者/总监指派）
- **状态**：open（总监已口头同意列入 backlog，待正式派工）
- **优先级**：normal
- **日期**：2026-09-20

---

## 我遇到的现象

T21 健康插件按卡交付：当 `followup_needed=true` 或手动 `POST .../request-followup` 时，
`event_bus.publish("health.care.requested", payload={...})` **已发出**（测试可捕获 payload）。

但 **todo 模块当前没有订阅该事件**，因此不会自动 `todo.item.write` 生成跟进项。
T21 报告已如实标注：「事件已发出、消费方待接」——这不是 health 侧 bug，是消费方尚未接线。

## 为什么这会挡住我

- 里程碑语义「健康 → 待办联动」只完成了一半（生产侧）；
- 主人在健康里勾了「需跟进」，若 todo 无反应，体验像功能坏了。

## 我认为应该怎么改

在 **todo 插件领地内**（我不改 T06 源码）：

1. 订阅 `health.care.requested`；
2. 映射为待办创建，建议字段：
   - `title`：`跟进：{health.title}` 或沿用 payload.title
   - `due_at`：`suggest_due`（ISO date，按 Asia/Shanghai 解释；空则默认 +3 天）
   - `source` / tags：`health`
3. **幂等**：用 payload `idempotency_key`
   `health-followup:{record_id}:{due|none}` 去重，避免同一跟进刷多条待办；
4. 仍遵守 ADR-0002：todo **不 import health**，只消费事件。

## 建议的验证方式

1. 在 health 建 `followup_needed=true` 的记录；
2. 断言 todo 出现一条待办，且 `idempotency_key` 对应记录不重复建第二条；
3. 再次 `request-followup` 同一 key → 不新增待办（或按产品语义更新，需在卡里写死一种）。

---

*草案由 Xiaomi MiMo 提交；建卡/派工归 Zcode（项目总监）。*
