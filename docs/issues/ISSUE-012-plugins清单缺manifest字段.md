# ISSUE-012 · /api/v1/plugins 清单缺 manifest 字段（插件贡献挂载结构性阻塞）

> **用途**：跨 agent 提问题 / 报障碍 / 要求别人改东西。
> **规矩**：永远不要直接修改别人的目录。需要对方改，就在这里写一张卡。
> **文件命名**：`ISSUE-012-plugins清单缺manifest字段.md`

- **提出者**：astrbot（取证）→ Doubao（复核/UI 实证）→ hermes（独立验证 + 立卡）
- **影响谁**：前端 kernel（`apps/web/src/kernel/plugins/**`）· 后端 core/plugins（`services/api/core/plugins/**`）· **E5 / D1 / 三线共同阻塞**
- **状态**：**fixed**（2026-09-23 前后端合拢：后端 `list_plugins()` 带 manifest + 前端可选链防御，门禁双 PASS）
- **优先级**：P0（生产结构性阻塞）
- **日期**：2026-09-23

---

## 现象

`/api/v1/plugins`（带 Bearer）返回 18 项插件，但**每项都没有 `manifest` 字段** → 前端 `p.manifest.entry` 必抛 `TypeError: Cannot read properties of undefined (reading 'entry')` → `syncPluginsToStore` 抛错 → `registerContributions` 所在循环不执行 → **插件扩展点贡献（E5 sidecar / D1 dashboard.card / DEG-01 软依赖角标）生产结构性无法挂载**。

症状：「界面看着正常（dock 图标有），但插件贡献就是不出现」。

## 三层证据链（三方独立证实）

| 层 | 证据 | 证实者 |
|:--|:--|:--|
| 接口层 | `/api/v1/plugins` 200 · 首项键集无 `manifest` | astrbot → Doubao → hermes |
| 逻辑层 | 复现 `p.manifest.entry` → `TypeError` | Doubao + hermes |
| UI 层 | 生产开 calendar 窗 → 无任何 sidecar 卡（截图在案） | Doubao |

## 根因

`services/api/core/plugins/manager.py:48` `list_plugins()` 组装输出时逐项用了 `p.manifest.get("name")` 等，**漏了把整个 `manifest` 字典放进输出**。

## 修法（前后端合拢）

| 半边 | 改动 | 归属 |
|:--|:--|:--|
| ① 后端 | `list_plugins()` 每项加 `"manifest": p.manifest` | hermes（已入库待部署） |
| ② 契约测试 | 断言每项含 manifest 且 entry/window/slots 可读（2 条） | hermes（11/11 绿） |
| ③ 前端防御 | `PluginContext.tsx`/`PluginRegistry.ts` 可选链 + 跳过无 manifest 项（3 例测试） | Doubao（88/88 绿） |

**关键语义**：前端必须用可选链（`p.manifest?.entry`）——18/19 有 entry，但 auth 这类纯 API 插件**合法无 UI 入口**。

## 判据

- [x] `/api/v1/plugins` 每项含 manifest（本地实测 19/19）
- [x] 前端对缺 manifest 项不崩、跳过不打断（plugins 9/9）
- [x] 契约测试钉住（test_plugins +plugins.test）
- [ ] 生产实测：部署后 E5 sidecar / D1 双形态出现（待部署批次）

## 验证记录

- test_plugins.py 11/11 passed · plugins.test.tsx 9/9 passed · 契约测试 2+3 条新增全绿

— hermes 立卡 + 修复 · 2026-09-23 · 三线阻塞解除