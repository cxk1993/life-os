import { useEffect } from "react";

/**
 * 全局快捷键。combo 形如：'escape' / 'mod+k' / 'mod+w' / 'shift+mod+p'。
 * 'mod' 在 Windows/Linux = Ctrl，在 macOS = Cmd（Meta）。
 */

interface ParsedCombo {
  key: string;
  needMod: boolean;
  needShift: boolean;
  needAlt: boolean;
}

export function parseCombo(combo: string): ParsedCombo {
  const parts = combo.toLowerCase().split("+");
  const key = parts[parts.length - 1];
  return {
    key,
    needMod: parts.includes("mod"),
    needShift: parts.includes("shift"),
    needAlt: parts.includes("alt"),
  };
}

type Handler = (e: KeyboardEvent) => void;

/**
 * ★ T30（顺修 T02 疑点①）：裸键（无任何修饰键）在**可编辑元素**里不应触发全局快捷键。
 * 否则用户在任意输入框里按 Esc，全局处理器照样跑 → 把正在打字的窗口关掉。
 * 带修饰键的组合（mod+k / mod+w）不受此限制 —— 那些本来就该全局生效。
 */
function isEditableTarget(t: EventTarget | null): boolean {
  const el = t as HTMLElement | null;
  if (!el) return false;
  const tag = el.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || el.isContentEditable === true;
}

export function useHotkey(combo: string, handler: Handler, opts: { enabled?: boolean } = {}): void {
  useEffect(() => {
    if (opts.enabled === false) return;
    const { key, needMod, needShift, needAlt } = parseCombo(combo);
    const bare = !needMod && !needShift && !needAlt;
    const onKey = (e: KeyboardEvent) => {
      if (bare && isEditableTarget(e.target)) return; // ★ 先于 handler，零副作用
      const mod = e.ctrlKey || e.metaKey;
      if (needMod !== mod) return;
      if (needShift !== e.shiftKey) return;
      if (needAlt !== e.altKey) return;
      if (e.key.toLowerCase() !== key) return;
      handler(e);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [combo, handler, opts.enabled]);
}
