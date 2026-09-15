import { pluginHost } from "./ModuleRegistry";
import { useDesktopStore } from "./store";

/**
 * 底部模块坞。列出所有已注册模块；点图标 → 开窗（singleton 重复点=聚焦）。
 * 模块有打开的窗口时，图标亮起小圆点；被禁用时置灰且不可点。
 */
export function Dock() {
  const modules = useDesktopStore((s) => s.modules);
  const windows = useDesktopStore((s) => s.windows);
  const openIds = new Set(windows.map((w) => w.moduleId));

  return (
    <div className="dock" role="toolbar" aria-label="模块坞">
      {Object.values(modules).map((reg) => {
        const m = reg.manifest;
        const open = openIds.has(m.id);
        const cls = [
          "dock__item",
          open ? "dock__item--open" : "",
          reg.enabled ? "" : "dock__item--disabled",
        ]
          .filter(Boolean)
          .join(" ");
        return (
          <button
            key={m.id}
            type="button"
            className={cls}
            aria-label={m.name}
            disabled={!reg.enabled}
            onClick={() => {
              if (reg.enabled) pluginHost.open(m.id);
            }}
          >
            {open ? <span className="dock__dot" aria-hidden="true" /> : null}
            <span className="dock__icon">{m.icon ?? m.name.slice(0, 1)}</span>
            <span className="dock__label">{m.name}</span>
          </button>
        );
      })}
    </div>
  );
}
