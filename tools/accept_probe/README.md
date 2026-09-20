# tools/accept_probe · L2 验收判据自动化套件

> **署名**：Qoder CN（L2 真机验收席）｜ **开工**：2026-09-20 12:05（领地公告帖在先）
> **依据**：总监令8 §3（灵感《L2 验收判据自动化套件》准奏 + 三工程约束）

## 用法

```bash
# 口令只走环境变量（绝不写入文件/回帖/日志）
export LIFEOS_ADMIN_PASSWORD=…
python tools/accept_probe/probe.py --target production --suite all      # 全套件
python tools/accept_probe/probe.py --target production --suite gate     # A6 三快腿
python tools/accept_probe/probe.py --target production --suite hash     # 入口基线
python tools/accept_probe/probe.py --target production --suite modules  # 坞 census
python tools/accept_probe/probe.py --target production --suite docsprobe # 根计数
python tools/accept_probe/probe.py --target production --suite deploycheck  # 部署后四合一
```

退出码：`0` 全绿 ｜ `1` 有判据未过 ｜ `2` 用法/输入错误。可 `set -e` 串进部署 runbook。

## 套件 ↔ 判据来源映射（约束3：来源可溯）

| 套件 | 判据 | 出处 |
|:--|:--|:--|
| `gate` | login 200 / refresh cookie 可存且**零 Secure** / refresh 200 / `/me` sub=admin | ACCEPT-T30 A6 三快腿（02:23 全验判定帖 §1；02:53 延迟探针加固；11:4x 路线A 对表复绿） |
| `hash` | 入口 `index-*.js` = 基线 | hash 链（02:36 判定帖 §5 追记 → 令8 §4 12:00 快照未漂移） |
| `modules` | 计数 17 + id 集合 | 令8 §4 生产三项快照（12:00）；11:4x 本席逐数 id 复验 |
| `docsprobe` | 活跃人格根=1、日记根=1（根合计 2） | BUG-T16-1 销账 + T17 幂等线上（MiMo 09:15 盘点 / hermes 10:26 三合一眼验 / 本席 API 对表） |
| `deploycheck` | healthz + gate + modules + hash 四合一 | 部署留痕帖的标准复核动作（ISSUE-006 路线A 对表首用） |

## 契约纪律（约束2：expected.json 即契约）

- `expected.json` 是**唯一期望值源**；任何变动必须**回帖说明并 @总监 + @知默台账**，禁止静默放宽（历史教训：判据被「顺手放宽」）；
- 未实测验证的项一律 `enabled=false`（如 local 18000 开发实例），不得凭猜测置真；
- 判据期望值变更时，同帖附「旧值→新值+依据」。

## 边界与安全

- **🖥 腿边界（令8 §3.3）**：本套件只做 **API 级 census + hash 对表**；浏览器 DOM 级断言（开窗/渲染/console 零错）归 hermes 真机腿，**不 jsdom 化**（防 flake）；
- **只读**：零生产写入、零三方依赖（stdlib）；
- **凭证纪律**：口令只经 `LIFEOS_ADMIN_PASSWORD` 环境变量/`--password` 进程内存传入；token/cookie 全程内存不落盘；
- **领地**：仅本目录三个文件；`tools/deploy_package_preflight.py`（TX-TOOL-01）与其它 `tools/*` 不碰。

## 已知边界（v1）

- `docsprobe` 依赖 `/api/v1/docs/nodes` 当前响应形态（list 或 `{nodes:[]}` 均已适配）；形态若变，套件报「根合计」异常即预警；
- `hash` 只提取 `index-*.js`（入口束），不覆盖 chunk 级 hash；
- 被嵌页握手（B2 情形 B）机器判据 B2-2/3/4 属另一交付（候归卡派定），不在本目录。
