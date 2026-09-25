/**
 * 壁纸应用与设置面板（V1-EXT2 · 见 wallpaper.ts 顶部说明）。
 * applyWallpaper：把四态配置落到 .desktop 的 CSS 变量；openWallpaperSettings：
 * 拉起设置弹层（模式四选 + 取色 + 图片选择 + 恢复默认）。
 */
import { createElement } from "react";
import { createRoot, type Root } from "react-dom/client";

export interface WallpaperConfig {
  mode: "grid" | "image" | "color" | "off";
  /** color 模式的自定义色（css color 值）；image/其余态忽略。 */
  color?: string;
  /** 运行时解析出的图片 URL（objectURL），不持久化。 */
  resolvedUrl?: string;
}

/** 四态 → .desktop CSS 变量（desktop.css `--wp-*` 组，见样式段）。 */
export function applyWallpaper(cfg: WallpaperConfig): void {
  const root = document.querySelector<HTMLElement>(".desktop");
  if (!root) return;
  root.dataset.wp = cfg.mode;
  if (cfg.mode === "image" && cfg.resolvedUrl) {
    root.style.setProperty("--wp-image", `url("${cfg.resolvedUrl}")`);
  } else {
    root.style.removeProperty("--wp-image");
  }
  if (cfg.mode === "color" && cfg.color) {
    root.style.setProperty("--wp-color", cfg.color);
  } else {
    root.style.removeProperty("--wp-color");
  }
}

/* ───────── 设置弹层（命令式挂载，与窗管零耦合） ───────── */

interface SettingsHost {
  current: WallpaperConfig;
  onPick: (file: File) => void | Promise<void>;
  onChange: (cfg: WallpaperConfig) => void;
}

let activeRoot: Root | null = null;
let activeHost: HTMLElement | null = null;

function closeSettings(): void {
  activeRoot?.unmount();
  activeRoot = null;
  activeHost?.remove();
  activeHost = null;
}

function SettingsPanel({ host }: { host: SettingsHost }) {
  const cfg = host.current;
  const modes: Array<{ key: WallpaperConfig["mode"]; label: string; hint: string }> = [
    { key: "grid", label: "淡线网格", hint: "默认" },
    { key: "image", label: "自定义图片", hint: "本机图片" },
    { key: "color", label: "自定义纯色", hint: "取色器" },
    { key: "off", label: "关闭背景", hint: "纯底" },
  ];
  return createElement(
    "div",
    {
      className: "wp-settings",
      role: "dialog",
      "aria-label": "桌面个性化",
      onClick: (e: React.MouseEvent) => e.stopPropagation(),
    },
    createElement("div", { className: "wp-settings__title" }, "桌面个性化"),
    createElement(
      "div",
      { className: "wp-settings__modes", role: "radiogroup", "aria-label": "背景模式" },
      modes.map((m) =>
        createElement(
          "button",
          {
            key: m.key,
            type: "button",
            role: "radio",
            "aria-checked": cfg.mode === m.key,
            className: `wp-settings__mode${cfg.mode === m.key ? " wp-settings__mode--active" : ""}`,
            onClick: () => host.onChange({ ...cfg, mode: m.key }),
          },
          createElement("span", { className: "wp-settings__mode-label" }, m.label),
          createElement("span", { className: "wp-settings__mode-hint" }, m.hint),
        ),
      ),
    ),
    cfg.mode === "image"
      ? createElement(
          "div",
          { className: "wp-settings__row" },
          createElement("input", {
            type: "file",
            accept: "image/*",
            "aria-label": "选择背景图片",
            onChange: (e: React.ChangeEvent<HTMLInputElement>) => {
              const f = e.target.files?.[0];
              if (f) void host.onPick(f);
            },
          }),
          createElement("span", { className: "wp-settings__hint" }, "图片仅存本机（IndexedDB），不上传"),
        )
      : null,
    cfg.mode === "color"
      ? createElement(
          "div",
          { className: "wp-settings__row" },
          createElement("input", {
            type: "color",
            "aria-label": "选择背景颜色",
            defaultValue: cfg.color || "#0e1116",
            onChange: (e: React.ChangeEvent<HTMLInputElement>) =>
              host.onChange({ ...cfg, color: e.target.value }),
          }),
        )
      : null,
    createElement(
      "div",
      { className: "wp-settings__row" },
      createElement(
        "button",
        {
          type: "button",
          className: "wp-settings__reset",
          onClick: () => host.onChange({ mode: "grid", color: "" }),
        },
        "恢复默认（淡线网格）",
      ),
      createElement(
        "button",
        { type: "button", className: "wp-settings__close", onClick: closeSettings },
        "关闭",
      ),
    ),
  );
}

export function openWallpaperSettings(host: SettingsHost): void {
  closeSettings();
  // 点面板外关闭（面板内 click 已 stopPropagation；once 触发后自清，activeHost 空时安全跳过）
  const dismiss = (e: MouseEvent) => {
    if (activeHost && !activeHost.contains(e.target as Node)) closeSettings();
  };
  activeHost = document.createElement("div");
  activeHost.className = "wp-settings-host";
  document.body.appendChild(activeHost);
  activeRoot = createRoot(activeHost);
  activeRoot.render(createElement(SettingsPanel, { host }));
  document.addEventListener("click", dismiss, { once: true });
}
