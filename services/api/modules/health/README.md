# 健康插件（T21）

症状 / 用药 / 复诊 / 体检记录。需要跟进时 publish `health.care.requested`，
由 **todo 自行订阅**生成跟进项 —— 本插件 **绝不 import todo**。

## API（`/api/v1/health`）

| 方法 | 路径 | 说明 |
|:--|:--|:--|
| GET | `/health` `/manifest` | 探针 / 清单 |
| GET | `/records?kind=&from=&to=&followup_only=` | 列表 |
| POST | `/records` | 新建；`followup_needed=true` 时发事件 |
| GET/PATCH/DELETE | `/records/{id}` | 详情 / 更新 / 删除 |
| POST | `/records/{id}/request-followup` | 手动再触发事件 |

## 事件

`health.care.requested` payload：`record_id / kind / title / suggest_due / source / idempotency_key`

`idempotency_key = health-followup:{record_id}:{due|none}`

## 联动状态

截至交付：**事件已发出、消费方待接**（todo 尚未默认订阅 `health.care.requested`）。
要默认订阅请另开 issue/小卡，不改 T06 源码。
