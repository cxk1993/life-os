/** MCP 控制台入口（T14 加载器按 manifest.entry = "@apps/mcp" 加载）。 */
import type { ComponentType } from "react";
import McpConsoleApp from "./McpConsoleApp";

const PluginModule = {
  manifestId: "mcp",
  Component: McpConsoleApp as ComponentType,
  slots: {
    "settings.page": McpConsoleApp as ComponentType,
  },
};

export default PluginModule;
export { McpConsoleApp };
