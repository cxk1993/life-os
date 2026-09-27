# course（插件 id：`course`）

课程表插件：**一行 = 一门课的一个上课时段**（课名 / 教师 / 地点 / 星期 / 节次 / 周次）。

| 项 | 值 |
|:--|:--|
| id | `course` |
| kind | `builtin` |
| API 前缀 | `/api/v1/course` |
| 表名前缀 | `course_` |
| 迁移目录 | `api/migrations/` |
| 挂载点 | 前端 `CourseApp` 挂在 **schedule 容器第 4 页**（DOCK_MERGE: course → schedule）|

## 端点

| 方法 | 路径 | 说明 |
|:--|:--|:--|
| GET | `/items` | 课程列表（可 `?weekday=0..6` / `?enabled_only=true`）|
| POST | `/items` | 新建课程时段 |
| GET | `/items/{id}` | 单条 |
| PATCH | `/items/{id}` | 局部更新 |
| DELETE | `/items/{id}` | 删除 |
| GET | `/week` | **一周网格**（前端主视图；`?date=` 指定周内任意一天）|
| GET | `/due/scheduler` | 上课提醒调度状态 |
| POST | `/due/tick` | 手动触发一轮提醒扫描 |

## 上课提醒（复用 calendar/todo 三段式）

```
remind_scheduler 扫「即将上课」→ event_bus.publish("course.session.due")
  → push.link 监听 → web push（浏览器 / PWA）
```

env 开关（默认关，与 calendar/todo 同款纪律）：

| 键 | 默认 | 说明 |
|:--|:--|:--|
| `COURSE_REMIND_ENABLED` | `false` | 总开关 |
| `COURSE_REMIND_LEAD_MINUTES` | `15` | 上课前多少分钟提醒 |
| `COURSE_REMIND_POLL_SECONDS` | `60` | 扫描周期 |

## 周次表达式

`weeks` 支持 `1-16` / `1,3,5-16` / `2-16双`（双周）/ `1-15单`（单周）；**空 = 每周都上**。
`term_start` 给「学期第一周周一」（YYYY-MM-DD）后，网格会按真实日期换算当前教学周。

## 改这个插件时不许做的事

1. 不许 import 别的插件 —— 走事件总线 / 对方公开 API / 扩展点
2. 不许 join 别人的表 —— 要数据就调对方的 API，并在 manifest.requires 里声明
3. 不许自己写登录 —— 内核统一注入 `Authorization: Bearer ***`
4. 不许写死颜色 —— 只用设计令牌（`var(--accent)` 之类）
5. 不许改 `kernel/` 或 `core/` —— 那是框架的 bug，去 `docs/issues/` 写卡
