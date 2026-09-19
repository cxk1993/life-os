import { useState } from "react";
import { Tabs } from "@/shared/components/Tabs";
import ToolExplorer from "./ToolExplorer";
import PatManager from "./PatManager";
import CallLog from "./CallLog";
import "./mcp.css";

type View = "tools" | "pats" | "log";

const TABS: { id: View; label: string }[] = [
  { id: "tools", label: "暴露的工具" },
  { id: "pats", label: "PAT 管理" },
  { id: "log", label: "调用日志" },
];

/**
 * MCP 控制台主界面（settings.page 扩展点）。
 * 三块：AI 能干什么（tools）/ 发什么钥匙（pats）/ 干过什么（log）。
 */
export default function McpConsoleApp() {
  const [view, setView] = useState<View>("tools");

  return (
    <div className="mcp-root">
      <div className="mcp-head">
        <div className="mcp-head__title">MCP · AI 能力入口</div>
        <div className="mcp-head__sub">
          插件 manifest 的 <code>provides</code> 自动映射为 MCP 工具，AI 客户端凭 PAT 调用。
        </div>
      </div>
      <Tabs tabs={TABS} active={view} onChange={(id) => setView(id as View)} />
      {view === "tools" && <ToolExplorer />}
      {view === "pats" && <PatManager />}
      {view === "log" && <CallLog />}
    </div>
  );
}
