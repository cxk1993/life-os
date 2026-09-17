# 本机笔记桥（services/bridge）

跑在主人 **Windows 本机** 上的独立 FastAPI 服务，只监听 `127.0.0.1`，
经 **frpc 隧道**暴露到云服务器。云服务器侧 `services/api/modules/notes/` 通过签名请求拉取索引与全文。

## 端点（内网隧道，仅服务器可访问）

| 方法 | 路径 | 说明 |
|:--|:--|:--|
| GET  | `/bridge/healthz` | 存活 + 版本 + 库列表 |
| GET  | `/bridge/libs` | 库配置（含 md 数量） |
| GET  | `/bridge/scan?lib=&limit=` | 全量索引（流式 ndjson，大库不 OOM） |
| GET  | `/bridge/read?lib=&path=` | 读全文（content + mtime + hash） |
| GET  | `/bridge/changes?since=` | 增量变化（供增量索引） |
| POST | `/bridge/write` | 写回（v0.1 默认 403，仅 mode=rw 放行） |

## 鉴权（所有 /bridge/* 必须带）

| Header | 说明 |
|:--|:--|
| `X-Bridge-PSK` | 预共享密钥（与服务器侧 `.env` 的 `BRIDGE_PSK` 一致） |
| `X-Bridge-Ts` | Unix 时间戳（秒），偏差 > 60s 拒绝 |
| `X-Bridge-Nonce` | 随机串，5 分钟内不可重放 |
| `X-Bridge-Sign` | `HMAC-SHA256(PSK, "{METHOD}\|{path?query}\|{ts}\|{nonce}\|{body}")` |

缺 / 错 PSK、错签名、过期时间戳、重放 nonce —— 一律 401。
路径穿越（`../../`）—— 400。

## 安装为 Windows 服务（随系统自启）

用 **nssm**（不要用 schtasks，已踩坑 3 小时）：

```powershell
nssm install lifeos-bridge "E:\ai work\work\life\services\api\.venv\Scripts\python.exe"
nssm set lifeos-bridge AppParameters "-c import sys; sys.path.insert(0, r'E:\ai work\work\life\services'); from bridge.main import create_bridge_app; import uvicorn; uvicorn.run(create_bridge_app(), host='127.0.0.1', port=8790)"
nssm set lifeos-bridge AppDirectory "E:\ai work\work\life\services\bridge"
nssm set lifeos-bridge AppEnvironmentExtra BRIDGE_PORT=8790 BRIDGE_PSK=**** BRIDGE_CONFIG=E:\ai work\work\life\services\bridge\config.yaml
nssm start lifeos-bridge
```

或直接双击 `run.ps1`（同样只监听 127.0.0.1）。

## 安全要点

- **绝不监听 0.0.0.0**：frp 只隧道 `127.0.0.1:8790`。
- **PSK 只走环境变量** `BRIDGE_PSK`，不写进 `config.yaml` 明文、不进代码。
- 响应里只回 `lib + POSIX 相对路径`，绝不回本机绝对路径。
- 只存索引与摘要，不把全文传到服务器（按需经隧道拉取）。

## 默认库

见 `config.yaml`：`main`（主仓库）/ `review`（work review 日报）/ `undo`（复盘）默认启用；
`claude`（云昔专用文件夹）默认 `enabled: false`，主人自行打开。

> ⚠️ 本机没有真实 Obsidian vault 的自动化接入验证：真实 vault 接入需人工在主人机器上确认。
