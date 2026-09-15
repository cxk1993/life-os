import { Desktop } from "@/kernel/Desktop";

/**
 * 应用根组件。窗口系统（Desktop + WindowManager + Dock + TopBar）由 T02 接入，
 * 替代最初的空壳页面。内核不认识任何业务，只负责「桌面与窗口」。
 */
export default function App() {
  return <Desktop />;
}
