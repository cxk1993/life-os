/**
 * 知识库插件入口（T14 加载器按 manifest.entry = "@/apps/knowledge" 加载）。
 * 主人 ⑤：复盘/笔记/文档 三合一（容器型模块，照 system/growth 样板）。
 */
import type { ComponentType } from "react";
import KnowledgeApp from "./KnowledgeApp";

const PluginModule = {
  manifestId: "knowledge",
  Component: KnowledgeApp as ComponentType,
  slots: {},
};

export default PluginModule;
export { KnowledgeApp };
