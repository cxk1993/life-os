import { useEffect } from "react";
import { Desktop } from "@/kernel/Desktop";
import { initWallpaper } from "@/kernel/wallpaper";

/**
 * 应用根组件。窗口系统（Desktop + WindowManager + Dock + TopBar）由 T02 接入，
 * 替代最初的空壳页面。内核不认识任何业务，只负责「桌面与窗口」。
 */
export default function App() {
  // V1-EXT2：桌面个性化（壁纸四态 + 桌面空白右键菜单）——
  // 状态自持（localStorage + IndexedDB），零壳层侵入，不动 store/Desktop。
  useEffect(() => initWallpaper(), []);
  return <Desktop />;
}
