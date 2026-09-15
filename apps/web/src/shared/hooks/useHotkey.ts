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

export function useHotkey(combo: string, handler: Handler, opts: { enabled?: boolean } = {}): void {
  useEffect(() => {
    if (opts.enabled === false) return;
    const { key, needMod, needShift, needAlt } = parseCombo(combo);
    const onKey = (e: KeyboardEvent) => {
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
