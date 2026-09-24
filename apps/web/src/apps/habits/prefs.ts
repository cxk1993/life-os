/** 习惯窗 · 用户自定义偏好（localStorage，插件私有键）。 */
export interface HabitsPrefs {
  showArchived: boolean;
}

const KEY = "lifeos.plugin.habits.prefs";

export function loadPrefs(): HabitsPrefs {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return { showArchived: false };
    const p = JSON.parse(raw) as Partial<HabitsPrefs>;
    return { showArchived: Boolean(p.showArchived) };
  } catch {
    return { showArchived: false };
  }
}

export function savePrefs(p: HabitsPrefs): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(p));
  } catch {
    /* 存储异常忽略 */
  }
}
