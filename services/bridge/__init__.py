"""services/bridge：跑在主人本机 Windows 上的笔记桥（独立 FastAPI 服务）。

★ 不是插件。只监听 127.0.0.1，经 frpc 隧道暴露在服务器侧。
★ 任何真实密钥（PSK）都从环境变量 BRIDGE_PSK 读，不进代码、不进 config.yaml 明文提交。
"""
