import { useHotkey } from "@/shared/hooks/useHotkey";

/**
 * 全局快捷键（验收 §7）。
 *   - Ctrl/Cmd+K ：唤起全局搜索
 *   - Esc        ：关闭当前窗口（搜索打开时先关搜索）
 *   - Ctrl/Cmd+W ：关闭当前窗口
 *   - Alt+Tab    ：在打开的窗口间循环聚焦（系统可能拦截，属浏览器限制）
 */

export interface ShortcutHandlers {
  onToggleSearch: () => void;
  onEscape: () => void;
  onCloseWindow: () => void;
  onCycleWindow: () => void;
}

export function useShortcuts(h: ShortcutHandlers): void {
  useHotkey("mod+k", (e) => {
    e.preventDefault();
    h.onToggleSearch();
  });
  useHotkey("escape", () => h.onEscape());
  useHotkey("mod+w", (e) => {
    e.preventDefault();
    h.onCloseWindow();
  });
  useHotkey("alt+tab", (e) => {
    e.preventDefault();
    h.onCycleWindow();
  });
}
