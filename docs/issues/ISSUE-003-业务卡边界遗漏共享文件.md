# ISSUE-003 · 业务卡的边界遗漏了两个「必写但没授权」的共享文件

- **提出者**：编排者（云昔）
- **影响谁**：T05 / T06 / T07 / T08 / T10 / T12（以及后续 T09 / T11 / T13）
- **状态**：open
- **优先级**：**blocker**（每张业务卡都会因此无法让 `make verify` 变绿）
- **日期**：2026-09-16

---

## 我遇到的现象

每张业务卡的「边界（只能改这里）」都只列了三类路径，例如 T05：

```text
apps/web/src/apps/calendar/**, services/api/modules/calendar/**
contracts/modules/calendar.manifest.json
```

但有两处文件是这张卡**必须写**的，却**不在边界里**：

### 1）`services/api/tests/test_<id>.py`

卡的执行步骤表明确要求写测试、并要求跑 `pytest tests/test_calendar.py`，
但 `services/api/tests/` 不在任何卡的边界里。`docs/示例/calendar_event_示例.py`
与 T04 的先例都指向同一个落点。

### 2）`contracts/data-dictionary.md` 的「业务表」一节

`contracts/data-dictionary.md` 第 54 行起是「业务表（各插件自建；此处仅登记表名与必备索引）」，
里面**已经预先登记了** `calendar_event`（第 58 行）与 `todo_item`（第 59 行）——
说明设计意图就是"插件自己来登记自己的表"。但该文件同样不在任何卡的边界里。

而且 T04 留了一道守卫 `services/api/tests/test_db.py::test_dictionary_matches_models`
会去核对字典与模型是否一致（见 ISSUE-004 的另一半问题）。

## 为什么这会挡住我

**产出与授权直接矛盾**：卡被要求"写测试"，但写测试的目录不在授权范围内。
严格执行"只能改自己列出的路径"的 agent，只能选择：

- 要么越界（违反铁律，判定不通过）；
- 要么不写测试（验收过不了）。

第 4 批六卡并发时这条矛盾真实咬到了：T05 把测试写在了 `services/api/tests/test_calendar.py`
（**越过边界**），并额外在 `services/api/run_t05_tests.py`、仓库根目录留下临时脚本
`_probe*.txt` / `nul` —— 这些都是"没有合法落脚点"的副产物。

## 我认为应该怎么改

**不建议**放宽"只能改自己的目录"这条铁律（它是本项目的安全底线）。建议在**任务卡生成器**里
把这两个共享文件显式写进每张业务卡的边界，并加一句说明：

```text
边界（只能改这里）：
  apps/web/src/apps/<id>/**
  services/api/modules/<id>/**
  # 以下两个是**共享文件**，只在你需要时追加自己那一行/那一个文件，不要动别人的：
  services/api/tests/test_<id>.py          # 追加：本卡自己的测试文件（不改别人已存在的测试）
  contracts/data-dictionary.md             # 追加：只在「业务表」一节加自己的表名与索引
```

同时建议在卡的硬约束里写明"共享文件只允许**追加自己那一行**，禁止重写他人内容"。

## 建议的验证方式

1. 重跑 `python _tools/build_feeds.py` 重新装配投喂包；
2. 抽查 T05/T06 投喂包第 4.1 节，确认两个共享路径已列出且措辞是"追加、不覆盖"；
3. 用一张卡实际走一遍：它应当能在不越界的前提下写出 `tests/test_<id>.py`
   并让 `pytest tests/test_<id>.py` 跑起来。
