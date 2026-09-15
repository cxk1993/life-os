import { useCallback, useState } from "react";

/**
 * 与 localStorage 双向同步的 state。
 * 用于「刷新后记住」这类本地偏好（主题已由 theme.ts 单独处理，这里给通用场景）。
 */
export function useLocalState<T>(key: string, initial: T): [T, (v: T | ((prev: T) => T)) => void] {
  const [state, setState] = useState<T>(() => {
    try {
      const raw = localStorage.getItem(key);
      return raw === null ? initial : (JSON.parse(raw) as T);
    } catch {
      return initial;
    }
  });

  const set = useCallback(
    (v: T | ((prev: T) => T)) => {
      setState((prev) => {
        const next = typeof v === "function" ? (v as (p: T) => T)(prev) : v;
        try {
          localStorage.setItem(key, JSON.stringify(next));
        } catch {
          /* 忽略存储异常 */
        }
        return next;
      });
    },
    [key],
  );

  return [state, set];
}
