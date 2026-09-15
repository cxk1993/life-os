# Life-OS · 人生管理系统

> 单用户、可插拔、能陪你用四年的个人系统。
> **内核只提供框架，能力全部由插件长出来** —— 详见 [`docs/adr/0002-插件协议.md`](docs/adr/0002-插件协议.md)。

---

## 5 分钟上手

### 前置依赖

| 需要 | 版本 | 说明 |
|:--|:--|:--|
| **Node** | 20+（见 `.nvmrc`） | 前端构建与开发服务器 |
| **Python** | **3.11.x**（锁定，别用 3.12/3.13） | 后端运行时 |
| `make` | 可选 | **没有也能用**，见下方说明 |
| `docker` | 可选 | 只在服务器部署时需要，本机开发不需要 |

> **没有 `make` 怎么办？** 完全没问题。本机的 Win11 就没有 make，
> 所以项目入口的真实实现是跨平台脚本 `tools/task.py`，
> 根目录 `Makefile` 只是它的薄壳。两条路等价：
>
> ```bash
> make dev            # 有 make 的机器
> python tools/task.py dev     # 没有 make 也能跑（推荐）
> ```

### 三条命令跑起来

```bash
python tools/task.py setup    # 1. 首次：建 venv + 装前后端依赖（会慢一点）
python tools/task.py dev      # 2. 同时起前端与后端
python tools/task.py verify   # 3. 交付前自检：lint + test + 构建
```

起来之后：

| 地址 | 是什么 |
|:--|:--|
| http://localhost:5173 | 前端（开发服务器，改代码自动刷新） |
| http://localhost:8000/docs | 后端 API 文档（FastAPI 自动生成） |
| http://localhost:8000/healthz | 健康检查，返回 `{"ok":true}` |

`Ctrl+C` 会把前后端一起停掉。

### 全部命令

| 命令 | 作用 |
|:--|:--|
| `setup` | 建 venv + 装依赖（首次） |
| `dev` | 同时起前端 5173 与后端 8000 |
| `lint` | 前端 tsc + eslint + prettier ／ 后端 ruff + mypy |
| `test` | 前端 vitest ／ 后端 pytest |
| `verify` | **交付前必跑**：lint + test + 前端构建 |
| `build` | 前端产物（有 docker 时顺带建镜像） |
| `clean` | 清构建缓存，**`data/` 绝不动** |
| `new-plugin --id x --name "名字"` | 生成新插件骨架（T14 交付后可用） |

---

## 目录结构

```
life/
├─ apps/web/                  # 前端宿主：只提供"窗"，不含业务
│  └─ src/kernel/             #   ★ 内核：窗口 / 坞 / 顶栏         (T02)
│     ├─ plugins/             #   ★ 插件加载器（T14 领地，勿动）
│     └─ slots/               #   ★ 扩展点定义（T14 领地，勿动）
├─ services/api/              # 后端宿主：只提供"路由/鉴权/事件"，不含业务
│  ├─ main.py                 #   入口（T01 空壳，T03 接管）
│  ├─ core/                   #   配置/鉴权/日志/异常            (T03)
│  ├─ db/                     #   内核级模型与迁移              (T04)
│  └─ modules/<id>/           #   各插件的后端部分              (各插件卡)
├─ plugins/                   # 第三方插件投放目录
├─ services/bridge/           # 本机 Obsidian 桥（跑在主人电脑上） (T07)
├─ contracts/                 # ★ 契约：插件 Schema / OpenAPI / 数据字典（改动需 RFC）
├─ deploy/                    # 镜像 / nginx / 证书 / 备份脚本    (T13)
├─ docs/
│  ├─ adr/                    # 架构决策记录（含"被否决的方案 + 理由"）
│  ├─ issues/                 # 跨 agent 提问题用（不要直接改别人的目录）
│  ├─ verify/                 # 各任务块验收报告
│  └─ rfc/                    # 契约变更申请
├─ tools/task.py              # 项目唯一入口的真实实现
├─ docker-compose.yml         # 生产编排（两个服务，db 用卷不用容器）
└─ docker-compose.dev.yml     # 开发编排（可选，本机用不上）
```

---

## 我该先读哪份文档？

按你的身份挑：

| 你是谁 | 先读 | 再读 |
|:--|:--|:--|
| **我要开发某个模块** | 你收到的那张任务卡（含执行步骤表） | `docs/adr/0002-插件协议.md`（全项目宪法） |
| **我想知道为什么这么设计** | `docs/adr/0001-技术栈选型.md` | `docs/adr/0002-插件协议.md` |
| **我要写插件** | `docs/adr/0002-插件协议.md` | `contracts/`（Schema 与数据字典） |
| **我要改接口 / 表结构** | `docs/rfc/TEMPLATE.md` | `contracts/README.md`（**不许自己改契约**） |
| **我要部署到服务器** | `deploy/README.md` | `docker-compose.yml` |
| **我被什么东西挡住了** | `docs/issues/TEMPLATE.md` | —— |
| **我要验收别人交的活** | `docs/verify/TEMPLATE.md` 末尾的「三条快速判定」 | —— |

> ⚠️ **不要把整个任务书从头读一遍。** 读你需要的部分就够了 ——
> 长文档会让关键约束被稀释掉。

---

## 几条不可违反的铁律

1. **契约已冻结**：`contracts/**`、`manifest.json`、数据字典，改动必须走 `docs/rfc/`。
2. **不许改别人的目录**：需要对方改 → 去 `docs/issues/` 写卡。
3. **不许从零发明**：项目里有骨架就照着抄。
4. **密钥只进 `.env`**：绝不进代码、绝不进前端、绝不进 git。`.env.example` 只放占位符。
5. **时间一律带时区**：出入参 ISO8601（`2026-09-15T08:00:00+08:00`），库里存 UTC。
6. **颜色一律走设计令牌**：不写死色值。
7. **不做多用户**：这是单人系统，别加注册、权限组、邀请码。
8. **不许报假 done**：做不完就报 `partial` + 卡在哪；用 mock 数据冒充真实数据直接判定不通过。

完整清单见 `docs/adr/0002-插件协议.md` 的「硬规则」一节。

---

## 数据在哪

全部在 **`data/`** 一个目录里（SQLite + WAL）。

- **备份**：`sqlite3 data/lifos.db ".backup data/backups/lifos-<时间>.db"`（**不要直接 `cp`**）
- **迁移**：复制整个 `data/` 目录即可
- `data/` 已在 `.gitignore` 里，不会被提交

---

## 现在的状态

**T01（工程骨架）已完成**：目录结构、任务入口、前后端空壳、lint/test 链路、契约与文档占位。
业务功能一概没有 —— 它们由后续任务块以**插件**形式长出来。

下一步看 `docs/verify/T01-report.md` 末尾的「下一步」。
