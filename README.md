# Life-OS · 人生管理系统

> 单用户、可插拔、能陪你用四年的个人系统。
> **内核只提供框架，能力全部由插件长出来** —— 详见 [`docs/adr/0002-插件协议.md`](docs/adr/0002-插件协议.md)。

Life-OS 是一个**单人自托管**的个人工作台：窗口化的前端宿主 + 后端内核 + MCP 服务。
内核只管七件事——窗口 / 路由 / 鉴权 / 事件 / 数据 / 设置 / 扩展点；
日程、待办、习惯、理财、笔记、日记、健康、复盘……每一项能力都以**插件**形式长在内核之上。

---

## 设计取向

- **一切皆插件**：插件在 `manifest.json` 里声明自己的窗口、路由、权限与能力，内核机械地发现它们。
- **MCP 是 AI 的正门**：插件声明的能力会映射成 MCP 工具，外部 agent 可以像调用本地能力一样调用它们。
- **数据主权**：所有数据在一个 `data/` 目录里（SQLite + WAL），迁移 = 复制目录，备份 = 复制文件。

---

## 5 分钟上手

### 前置依赖

| 需要 | 版本 | 说明 |
|:--|:--|:--|
| **Node** | 20+（见 `.nvmrc`） | 前端构建与开发服务器 |
| **Python** | **3.11.x**（锁定，别用 3.12/3.13） | 后端运行时 |
| `make` | 可选 | **没有也能用**，见下方说明 |
| `docker` | 可选 | 只在服务器部署时需要，本机开发不需要 |

> **没有 `make` 也能用。** 项目入口的真实实现是跨平台脚本 `tools/task.py`，
> 根目录 `Makefile` 只是它的薄壳。两条路**行为完全一致**：
>
> ```bash
> make dev                     # 有 make 的机器
> python tools/task.py dev     # 任何机器都能跑（推荐，含 Windows 无 make 的情况）
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
| `new-plugin --id x --name "名字"` | 生成新插件骨架 |

---

## 目录结构

```
life/
├─ apps/web/                  # 前端宿主：只提供"窗"，不含业务
│  └─ src/kernel/             #   ★ 内核：窗口 / 坞 / 顶栏
│     ├─ plugins/             #   ★ 插件加载器
│     └─ slots/               #   ★ 扩展点定义
├─ services/api/              # 后端宿主：只提供"路由/鉴权/事件"，不含业务
│  ├─ main.py                 #   入口
│  ├─ core/                   #   配置/鉴权/日志/异常
│  ├─ db/                     #   内核级模型与迁移
│  └─ modules/<id>/           #   各插件的后端部分
├─ plugins/                   # 第三方插件投放目录
├─ services/bridge/           # 本机 Obsidian 桥
├─ contracts/                 # ★ 契约：插件 Schema / OpenAPI / 数据字典（改动需 RFC）
├─ deploy/                    # 镜像 / nginx / 证书 / 备份脚本
├─ docs/
│  ├─ adr/                    # 架构决策记录（含"被否决的方案 + 理由"）
│  ├─ issues/                 # 问题记录
│  ├─ specs/                  # 数据/接口规范
│  ├─ tutorials/              # 插件开发入门
│  └─ rfc/                    # 契约变更申请
├─ tools/task.py              # 项目唯一入口的真实实现
├─ docker-compose.yml         # 生产编排（两个服务，db 用卷不用容器）
└─ docker-compose.dev.yml     # 开发编排（可选，本机用不上）
```

---

## 我该先读哪份文档？

| 我想…… | 先读 | 再读 |
|:--|:--|:--|
| **知道为什么这么设计** | `docs/adr/0001-技术栈选型.md` | `docs/adr/0002-插件协议.md` |
| **写一个插件** | `docs/adr/0002-插件协议.md` | `docs/tutorials/plugin-dev-101.md` |
| **改接口 / 表结构** | `docs/rfc/TEMPLATE.md` | `contracts/README.md`（**不许自己改契约**） |
| **部署到服务器** | `deploy/README.md` | `docker-compose.yml` |
| **遇到了问题** | `docs/issues/TEMPLATE.md` | —— |

> ⚠️ **不要把整个仓库的文档从头读一遍。** 读你需要的部分就够了 ——
> 长文档会让关键约束被稀释掉。

---

## 几条不可违反的铁律

1. **契约已冻结**：`contracts/**`、`manifest.json`、数据字典，改动必须走 `docs/rfc/`。
2. **不许从零发明**：项目里有骨架就照着抄。
3. **密钥只进 `.env`**：绝不进代码、绝不进前端、绝不进 git。`.env.example` 只放占位符。
4. **时间一律带时区**：出入参 ISO8601（`2026-09-15T08:00:00+08:00`），库里存 UTC。
5. **颜色一律走设计令牌**：不写死色值。
6. **不做多用户**：这是单人系统，别加注册、权限组、邀请码。

完整清单见 `docs/adr/0002-插件协议.md` 的「硬规则」一节。

---

## 数据在哪

全部在 **`data/`** 一个目录里（SQLite + WAL）。

- **备份**：`sqlite3 data/lifos.db ".backup data/backups/lifos-<时间>.db"`（**不要直接 `cp`**）
- **迁移**：复制整个 `data/` 目录即可
- `data/` 已在 `.gitignore` 里，不会被提交

---

## 许可证

本项目采用 [Apache License 2.0](LICENSE) 许可。欢迎 fork、二次开发与商业使用，
保留版权与许可声明即可。

---

## 参与

- 想要的能力，欢迎以**插件**的形式提交：见 `docs/tutorials/plugin-dev-101.md`。
- 发现的问题、契约变更想法，走 `docs/issues/` 与 `docs/rfc/`。
