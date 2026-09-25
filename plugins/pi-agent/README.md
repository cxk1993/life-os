# Pi 智能体（插件 id：`pi-agent`）

> ★ **TX-FRAME-01** · 把整个 Pi agent 项目内嵌融合为 **Life-OS 的一个插件**。
> 指挥线：**主人 × astrbot**（总监令 10 §1）· 设计：本目录同源各帖（探讨帖 / 设计卡 v1·v2 / 选型帖）。

| 项 | 值 |
|:--|:--|
| id | `pi-agent` |
| kind | **`third-party`**（★ 可禁用、可卸载）|
| API 前缀 | `/api/v1/pi-agent` |
| 能力 | `pi.chat` · `pi.session.manage` |
| 权限 | `fs:plugin` · `net:out:localhost`（★ 总监令 10 红线③收口）|

---

## ★ 当前进度：**第①刀（骨架）**

**目标**：**只验证「pi 能被内核识别为一个 third-party 插件」** —— 可禁用、可卸载、**不改内核一行**（ADR-0002 唯一判据）。

| 做了什么 | 没做什么（刻意）|
|:--|:--|
| `manifest.json`（契约 + 收口权限 + lifecycle 钩子）| ❌ 不起 pi 子进程 |
| `api/router.py`（health / manifest / status）| ❌ 不接 MCP |
| `api/lifecycle.py`（**空壳**，只打日志）| ❌ 不写 UI |
| 本 README + 测试骨架 | ❌ 不碰 `kernel/` `core/` |

**判据**：J-21（不改内核）· J-22（可禁用）· J-23（可卸载无残留）。

---

## ★ 已定的关键设计（后续刀次用）

| 项 | 定案 |
|:--|:--|
| **接入方式** | ★ **RPC 模式**（`pi --mode rpc`，JSONL over stdin/stdout；官方有 Python 示例）|
| **模型** | ★ **`life-os` 路由**（`step-5-preview` + `agnes-3.0-flash` 自动故障转移）· 子 agent 复用 · 视觉兜底 `识图` · 思考强度 `high` |
| **对外口子** | ★ **零新造** —— 走 **ADR-0003 MCP 桥**（`provides` → MCP tools）+ **session 工具集**（`pi_session_new` / `pi_chat` / `pi_session_switch` / `pi_session_lock`）|
| **记忆** | ★ **Pi 用自己完整的记忆体系**（主人明确：无妨，不设限）|
| **降级** | ★ **L1 正常 / L2 重启中（快速失败不排队）/ L3 熔断 → 保底「轻量对话」**（workbuddy 拍砖口径）|
| **沙箱** | `gondolin`（micro-VM + **secret 占位符** = 零凭证纪律）|
| **前端** | ★ **自建**（保 tokens/主题一致性；`pi-web-ui` 仅作参考实现）|

---

## ★ 已知缺口（候内核补）

| 缺口 | 说明 |
|:--|:--|
| **`subprocess` 权限** | Pi 需起子进程，但内核 `permissions.py` 目前**只认字符串格式**（`db:own` / `net:out:<host>` / `fs:plugin` …），**没有 subprocess**；schema 里的"对象格式"（`filesystem`/`network`/`subprocess`）**内核尚未实现**。→ **第①刀刻意不起进程，正好规避**；接 RPC 前需内核补此权限。 |

---

## 改这个插件时不许做的事（照 ADR-0002 硬规则）

1. 不许 import 别的插件 —— 走事件总线 / 对方公开 API / 扩展点
2. 不许 join 别人的表 —— 要数据就调对方 API，并在 `manifest.requires` 里声明
3. 不许自己写登录 —— 内核统一注入 `Authorization: Bearer <jwt>`
4. 不许写死颜色 —— 只用设计令牌（`var(--accent)` 之类）
5. 不许改 `kernel/` 或 `core/` —— 那是框架的 bug，去 `docs/issues/` 写卡
6. ★ **不许用相对导入** —— 第三方插件按文件路径加载（详见 `api/router.py` 顶部注释）
