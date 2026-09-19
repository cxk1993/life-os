# ISSUE-005 方案详评 · 内核「受限 api client」注入（三案深入评估）

> **作者**：hermes（汐瑶）—— T17 发现者 + 现行权宜实现者
> **日期**：2026-09-19 深夜
> **状态**：供主人 / Zcode 裁决
> **关联**：`ISSUE-005-内核缺受限api-client注入.md`（issue 正文）、`T17-report.md` §偏差 1

---

## 0. 一句话

**问题不是「要不要跨插件调 API」（要，ADR-0002 已定），而是「用什么通道调」——当前内核没有官方通道，每个插件自签 token + 自管 httpx，样板成本高、口径易散。**

本详评从 T17 实战（`_HttpxDocsAdapter` 已交付运行）出发，逐案评估，给出推荐排序。

---

## 1. 现状复盘（T17 的权宜实现，亲测的结论）

```python
class _HttpxDocsAdapter:
    def __init__(self, token, base="http://127.0.0.1:18000"):
        self._headers = {"Authorization": f"Bearer {token}"}
    # tree() / create() / patch() —— 三个方法，薄封装 httpx
```

**做得对的**：
1. **守住 ADR-0002 红线**：不 import、不 join 他表，纯 HTTP 调 docs API
2. **留了替换接口**：`DiaryService` 依赖 `DocsAdapter` Protocol，换实现零侵入
3. **测试/探测分离**：单测用 FakeDocsAdapter（纯逻辑），探测验真链路

**样板成本（真实发生的）**：
1. 每个新插件都要**重写一遍** httpx 封装（tree/create/patch 各自调）
2. 都要**自签 token**（`create_access_token(user.sub)`）——虽然单用户系统简单，但口径可能散
3. 都要处理 `INTERNAL_API_BASE` 环境变量 + 错误映射（docs 4xx → ValidationError）
4. **测试要写 Fake**（因为真链路需要起服务）——这个成本被低估了

---

## 2. 三案深入评估

### 方案 A：内核 `core/deps` 增加 `get_plugin_client` 注入（推荐评估）

**内容**：内核按 `manifest.requires` 校验后，发放**作用域受限**的内部调用 client。
即：`plugin_a` 调 `plugin_b` 的 API，由内核确认 `a` 的 requires 含 `b` 的能力，才发放可调 `b` 的 client。

| 维度 | 评估 |
|:--|:--|
| 对 ADR-0002 | ★ 最贴合：requires 声明 → 内核校验 → 放行，**把「声明即授权」变成机器强制** |
| 消除样板 | ★★ 插件侧只写 `client = get_plugin_client(db, "docs")` 即可；token/错误映射/环境变量全由内核管 |
| 测试友好 | ★ 内核注入可 mock（测试注入 Fake），不用起真服务 |
| 代价 | ⚠️ 动 **T03 内核领地**（`core/deps.py`）；需主人授权 + 小 RFC；T03 是已交付卡，属于「内核增强」 |
| 风险 | 低（新增依赖注入函数，不破坏现有 `get_db`/`get_current_user`） |
| 时间估计 | 0.5~1 天（含测试） |

**实施建议（若选 A）**：
```python
# core/deps.py 新增（示意）
def get_plugin_client(db: Session, target_plugin: str) -> PluginClient:
    """按当前插件 manifest.requires 校验后发放内部调用 client。"""
    # 1. 读当前插件 manifest 的 requires
    # 2. 校验 target_plugin 的能力在 requires 内（不在 → 403）
    # 3. 返回内部 client（自动带 token / 错误映射 / base_url）
```
- **归属**：T03 增补卡（或 ISSUE-005 承接卡），不走 T18
- **平滑替换**：diary 的 `_HttpxDocsAdapter` 换成 `get_plugin_client(db, "docs")`，Protocol 不变

### 方案 B：并入 T18 MCP Server

**内容**：T18 做「能力 → MCP 工具」时顺路统一内部调用通道。

| 维度 | 评估 |
|:--|:--|
| 顺路程度 | ⚠️ 表面顺路，实则**两个不同问题**：T18 是「对外暴露能力给 AI」，ISSUE-005 是「插件间内部调用」。混在一起 T18 会变大变杂 |
| workbuddy 意见 | ★ 他已明确「不顺手补」——卡上没写就不做，这是对的 |
| 风险 | 高（T18 体量增大、验收面扩大、可能拖慢判据②落地） |

**结论**：**不推荐**并入 T18。若担心两条线重复，可以在 T18 卡里加一行「内部调用走 ISSUE-005 的 A 方案产物」，而不是把实现塞进 T18。

### 方案 C：维持现状 + 共享参考实现（模板包/文档层）

**内容**：不动内核，把 T17 的 `_HttpxDocsAdapter` 抽象提取为**共享参考实现**（模板包 5 加一节「跨插件 HTTP 调用参考」）。

| 维度 | 评估 |
|:--|:--|
| 零内核改动 | ★ 安全，不需要主人授权 |
| 消除样板 | ⚠️ 只消除「复制粘贴」层面，不消除「自签 token / 环境变量 / Fake 测试」的认知负担 |
| 口径统一 | ⚠️ 靠文档约定，**不是机器强制**——requires 声明了但没调校验，还是可能调了未声明的能力 |

**结论**：**可作为 A 落地前的过渡**（先给后续插件一个标准姿势），但**不是终态**。

---

## 3. 推荐排序

| 排名 | 方案 | 理由 |
|:--|:--|:--|
| **①** | **A：内核 `get_plugin_client` 注入** | 最贴合 ADR-0002「声明即授权」，消除样板，机器强制口径。动 T03 内核是**增强不是破坏**，风险低 |
| ② | C：共享参考实现 | 零风险过渡；但治标不治本 |
| ③ | B：并入 T18 | 两个问题混在一起，不推荐 |

**我的建议**：**先做 C（立即可做，模板包加一节，我起草）作为过渡，同时提请主人授权 A（T03 增补卡）**。
这样后续插件（T20/T24/T25 等）先用标准姿势，A 落地后平滑替换。

---

## 4. 若选 A 的验收判据

1. `get_plugin_client(db, "docs")` 在 requires 含 docs 时返回 client，可调 docs API
2. requires **不含** docs 时调用 → 403（机器强制「声明即授权」）
3. 现有插件（diary）切换到 `get_plugin_client`，T17 探测 15/15 仍过
4. `core/deps.py` 新增函数不破坏现有 `get_db`/`get_current_user`（既有测试全绿）
5. 文档：模板包 5 加「跨插件调用」参考（C 案产物，A 落地前就用上）

---

## 5. 结论回写

- [x] 方案详评完成（2026-09-19 深夜，hermes）
- [x] 主人裁决：**A + C**（2026-09-20，主人授权动 T03 内核）
- [x] **A 案实装**：`core/deps.py` 新增 `get_plugin_client` + `InternalHttpClient`；diary 平滑切换；单测 6/6（`tests/test_plugin_client.py`）；真链路探测卡点已发帖求助
- [x] **C 案落地**：模板包5 §4「跨插件 HTTP 调用参考」（2026-09-20，hermes）
- [ ] A 案真链路探测通过 + Zcode 复测提交
- [ ] 若后续插件跨调用：一律走 `get_plugin_client`（模板 §4.2）
