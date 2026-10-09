# ISSUE-008 · MCP 适配层机械加s导致 2 工具调用必 404

> **建档**：hermes（汐瑶）｜ 2026-09-20 14:2x
> **来源**：Qoder CN《E7 完工帖》§3 BUG 候选上报 → 探针坐实
> **状态**：🟡 候选 P2 · **待拍板**

---

## 1. 现象

MCP 26 工具中 `dashboard_today_read`、`dashboard_system-health_read` 两个工具**调用必 404（isError）**；其余 24 工具不受影响。`tools/list` 层面看不出问题（列表展示无妨），**实际调用才炸**。

## 2. 根因（代码级实证，总监亲跑复核）

| 环节 | 位置 | 实测 |
|:--|:--|:--|
| 推导 path | `services/api/modules/mcp/registry_adapter.py:75` | `path = f"{api_base.rstrip('/')}/{resource}s"` —— **机械加复数 s** |
| 真实路由 | `services/api/modules/dashboard/router.py:67` | `@router.get("/today")`（**today 不加 s**） |
| 真实路由 | `services/api/modules/dashboard/router.py:75` | `@router.get("/health-of-system")`（vs 推导 `/system-healths`，**系统健康不是复数**） |
| 调用链 | `services/api/modules/mcp/mcp_server.py:124` | `forward(tool.method, tool.path, payload)` 直用推导 path |

推导：`dashboard.today.read` → `/api/v1/dashboard/todays`（错）→ 404
推导：`dashboard.system-health.read` → `/api/v1/dashboard/system-healths`（错）→ 404

## 3. 定性

- **代码级坐实**（非纸面推断）：三处源码逐行核过。
- **功能缺陷 P2**（非安全）：不影响其余 24 工具；PAT 已签发用户调用这 2 工具会拿到 isError。
- 无关 E7 文档质量：E7 的 26 工具映射表本身正确（按代码规则复算），此缺陷在**适配层推导规则**。

## 4. 修法建议（二选一，主人拍板）

| 方案 | 改法 | 改动面 | 风险 |
|:--|:--|:--|:--|
| **A · provides 改写** | dashboard 插件 manifest 的 provides 改单数资源名（如 provider 用 `dashboard.today.read` 但适配层不再机械加 s，或确认 `today` 本身就是单数资源语义） | manifest 1 处 + registry_adapter 规则对齐 | 需同步 E7 工具表/文档命名 |
| **B · 路由别名表** | `registry_adapter.py` 加 `path_alias` 表：`{"todays": "/today", "system-healths": "/health-of-system"}`，推导后查表覆盖 | 仅 adapter 1 处 | 治标，后续新路由仍可能踩机械 s |

**总监倾向**：**A 为主**（修规则治本，人工核对 26 工具名级路由后一次性对齐），B 留作兜底补丁。但 **T18/hermes 归口，下午（主人不在期）不动任何代码**——只出提案，主人归来拍板后按派单制执行。

## 5. 验收判据（执行时）

1. 本地：`derive_tool` 单测新增 2 例（today / health-of-system 命中别名或规则修正），全绿
2. 本地 MCP tools.list 26 工具名级不变（外部契约零漂移）
3. 本地 `tools/call` dashboard_today_read / dashboard_system-health_read 返回 200 非 isError
4. 生产（主人批准后）：PAT 最小授权实测调 2 工具 200

## 6. 边界

- 未动任何代码、未起生产实例、无凭证产生（Qoder 与总监均零动作）。
- 与 E7 文档的 26 工具表无冲突（工具名不变，仅 path 推导修）。

— hermes（汐瑶）· 第三任总监 🦊