# kernel/plugins/ —— ★ T14 的领地，不要在这里写实现

**这个目录归 T14（插件框架 · 扩展点与生命周期）所有。**

它的职责是"插件**如何被发现 / 加载 / 启停 / 授权 / 挂扩展点**"：

```
kernel/plugins/
├─ PluginRegistry.ts     # 插件注册表（装了什么、启没启、什么版本）
├─ PluginLoader.ts       # 发现 → 校验 manifest → 动态 import 入口
├─ PluginLifecycle.ts    # install / enable / disable / uninstall
├─ PluginPermissions.ts  # requires / provides 的能力声明校验（越权直接拒）
└─ PluginHost.ts         # 对外接口：窗口层只认这个形状
```

## 谁不能动这里

| 角色 | 能做 |
|:--|:--|
| **T02 前端内核** | 只读。它做"窗口与坞"，并把 `ModuleRegistry` 写成 `PluginHost` 的接口形状，让 T14 **直接顶替而不返工** |
| **T05–T12 各插件** | 只读。它们是被加载方，不是加载器 |
| **其它任何卡** | 只读。需要改 → 去 `docs/issues/` 写卡 |

## 为什么要单独划出来

「一切皆插件」是全项目的核心理念。如果这个目录被顺手改坏、或者被各卡各自发明一套加载方式，
这个理念就死了。它的可机器验证判据只有一条：

```bash
# 内核里不许出现业务词汇（含 apps/web/src/kernel 与 services/api/core）
grep -rniE "calendar|todo|notes|finance|habit" apps/web/src/kernel services/api/core
# 输出必须为空
```

> T01 只建了这个目录和这份说明。**一行实现都没有写** —— 那是 T14 的活。
