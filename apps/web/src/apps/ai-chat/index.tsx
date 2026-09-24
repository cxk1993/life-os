/**
 * ai-chat 插件入口（manifest.entry = "@/apps/ai-chat"）。
 */
import type { ComponentType } from "react";
import ChatApp from "./ChatApp";
import "./chat.css";

const PluginModule = {
  manifestId: "ai-chat",
  Component: ChatApp as ComponentType,
  slots: {},
};

export default PluginModule;
export { ChatApp };
