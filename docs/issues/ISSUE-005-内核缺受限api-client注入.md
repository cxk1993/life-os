# ISSUE-005 · 内核缺「受限 api client」注入机制 —— 跨插件 HTTP 调用无官方通道

- **提出者**：hermes（T17 实装中发现）+ Zcode（成文立卡，2026-09-19）
- **影响谁**：T03 内核（`services/api/core/deps.py`，领地所有者）/ T18 MCP Server（可能承接）/ 所有需要"调别的插件 API"的后续插件
- **状态**：✅ **已闭环（2026-09-20 凌晨）**——A 案 `ed92eef`（get_plugin_client + diary 切换，单测 6/6 + 真链路 16/16）+ C 案入模板包5 §4 并已传播全部投喂包；主人裁决 A+C 完整落地
- **优先级**：medium
- **日期**：2026-09-19

---

## 我遇到的现象

任务卡 T17 §API 契约写：「本卡**不直连 `docs_*` 表**，一律调 T15 的 `provides` 能力（**经内核注入的受限 api client**）」。
实装时发现：**内核 `core/deps` 并没有提供这个注入机制** —— 卡片假设了一个不存在的能力。

## 现行权宜（T17 已交付的实现，可用但不优雅）

hermes 的 `_HttpxDocsAdapter`：diary 后端用 **httpx 真请求本服务** `/api/v1/docs/...`：
- token 用当前用户身份**现签**（`create_access_token(user.sub)`），不落库、不复用；
- 内部地址走 `INTERNAL_API_BASE` 环境变量（默认 `http://127.0.0.1:18000`，已入 `.env.example`）；
- 测试用 FakeDocsAdapter 验逻辑，探测 15/15 验真链路。

**守住的红线**：插件间不 import、不 join 他表（ADR-0002）——语义合规，但每个插件都得自签 token + 自管 httpx，**样板成本高且口径易散**。

## 建议的方向（供裁决）

| 方案 | 内容 | 代价 |
|:--|:--|:--|
| A（推荐评估） | 内核 `core/deps` 增加 `get_plugin_client` 依赖注入：按 `manifest.requires` 校验后发放**作用域受限**的内部调用 client（免自签、免环境变量） | 动 T03 内核领地，需主人授权 + RFC 级小改 |
| B | 把它并入 T18 MCP Server 的范围（T18 本就要做"能力 → 工具"通道，顺路统一内部调用） | T18 体量增大；workbuddy 建议不"顺手补"，需明确写进卡 |
| C | 维持现状（各插件 httpx 自签），把 T17 的适配器抽象提取为**共享参考实现**（模板包/文档层，不动内核） | 零内核改动，但样板依旧 |

## 方案详评（2026-09-19 · hermes 起草，供主人/Zcode 裁决）

→ **`docs/issues/ISSUE-005-方案详评.md`**（A/B/C 三案深入评估 + 推荐排序 + 若选 A 的验收判据）

| 排名 | 方案 | 一句话 |
|:--:|:--|:--|
| ① | A：内核 `core/deps` 增加 `get_plugin_client` 注入 | 最贴合 ADR-0002「声明即授权」，机器强制口径；动 T03 内核属增强，风险低（0.5~1 天） |
| ② | C：模板包沉淀共享参考实现 | 零内核改动；只消除复制粘贴，不消除自签 token 认知负担；可作 A 落地前过渡 |
| ③ | B：并入 T18 MCP Server | 两个不同问题混在一起，T18 会变大变杂，不推荐 |

**hermes 建议**：先做 C（模板包 5 加「跨插件调用」参考节，我起草）作过渡，同时提请主人授权 A（T03 增补卡）。

## 关联

- T17 交接帖 §2（发现者）、`docs/verify/T17-report.md` §偏差 1
- ADR-0002（插件协议：跨插件只走 API + requires）
- `docs/issues/ISSUE-005-方案详评.md`（方案详评，hermes 起草 2026-09-19）
- 若采纳 A/B：`diary` 的 `_HttpxDocsAdapter` 可平滑替换（hermes 已留了适配器接口）
