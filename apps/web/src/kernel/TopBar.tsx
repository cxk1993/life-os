import { useEffect, useState } from "react";

import { useTheme } from "@/shared/styles/theme";
import { useDesktopStore } from "./store";

interface Props {
  onOpenSearch: () => void;
  onTidy: () => void;
}

function useClock(): string {
  const [now, setNow] = useState(() => formatNow());
  useEffect(() => {
    const t = setInterval(() => setNow(formatNow()), 1000);
    return () => clearInterval(t);
  }, []);
  return now;
}

function formatNow(): string {
  try {
    return new Date().toLocaleTimeString("zh-CN", { hour12: false });
  } catch {
    return "";
  }
}

/**
 * 顶栏：品牌 / 全局搜索入口 / 走秒时钟 / 整理桌面 / 主题切换。
 * 锁定的「登录相关」不在内核职责内（鉴权由 T03 提供），这里只留一个无副作用的占位按钮位。
 */
export function TopBar({ onOpenSearch, onTidy }: Props) {
  const theme = useTheme((s) => s.theme);
  const toggle = useTheme((s) => s.toggle);
  const clock = useClock();
  // ★ T23 工作区切换器
  const workspaces = useDesktopStore((s) => s.workspaces);
  const activeWorkspaceId = useDesktopStore((s) => s.activeWorkspaceId);
  const switchWorkspace = useDesktopStore((s) => s.switchWorkspace);
  const createWorkspace = useDesktopStore((s) => s.createWorkspace);

  return (
    <div className="topbar">
      <span className="topbar__brand">Life-OS</span>
      <button
        type="button"
        className="topbar__search"
        onClick={onOpenSearch}
        aria-label="打开全局搜索"
      >
        搜索…
        <kbd>Ctrl K</kbd>
      </button>

      {/* ★ T23：工作区页签 + 新建。名字一律「工作区 N」，内核零业务。 */}
      <div className="topbar__ws" role="tablist" aria-label="工作区">
        {workspaces.map((w) => (
          <button
            key={w.id}
            type="button"
            role="tab"
            aria-selected={w.id === activeWorkspaceId}
            className={`topbar__ws-tab${w.id === activeWorkspaceId ? " is-active" : ""}`}
            title={w.name}
            onClick={() => switchWorkspace(w.id)}
          >
            {w.name}
          </button>
        ))}
        <button
          type="button"
          className="topbar__ws-add"
          aria-label="新建工作区"
          title="新建工作区"
          onClick={() => createWorkspace()}
        >
          ＋
        </button>
      </div>

      <span className="topbar__spacer" />
      <span className="topbar__clock" aria-label="当前时间">
        {clock}
      </span>
      <div className="topbar__actions">
        <button
          type="button"
          className="icon-btn"
          aria-label="整理桌面"
          title="整理桌面"
          onClick={onTidy}
        >
          ⊞
        </button>
        <button
          type="button"
          className="icon-btn"
          aria-label={theme === "dark" ? "切换到亮色" : "切换到暗色"}
          title="切换主题"
          onClick={toggle}
        >
          {theme === "dark" ? "☀" : "☾"}
        </button>
      </div>
    </div>
  );
}
