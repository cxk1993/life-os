import type { ReactNode } from "react";

import { PluginBoundary } from "../plugins/PluginBoundary";
import { useSlotContributions } from "./contributions";
import { SLOTS } from "./slots";
import type { SlotName } from "../plugins/types";

/**
 * 插槽宿主：在某个扩展点的位置渲染所有已挂载的贡献。
 *
 * 用法（内核在桌面/坞/顶栏等预留位置调用）：
 *   <SlotHost slot="dashboard.card" />
 *
 * 每个贡献都用 PluginBoundary 单独兜错：单个插件炸了只灰它自己，桌面不白屏。
 * 没有贡献时渲染默认占位（或调用方提供的 fallback）。
 */
export interface SlotHostProps {
  slot: SlotName;
  /** 没有贡献时的兜底渲染。 */
  fallback?: ReactNode;
  className?: string;
}

export function SlotHost({ slot, fallback, className }: SlotHostProps) {
  const items = useSlotContributions(slot);
  const meta = SLOTS[slot];
  return (
    <div
      className={`slot slot--${slot}${className ? ` ${className}` : ""}`}
      data-slot={slot}
      role="region"
      aria-label={meta?.title}
    >
      {items.length === 0
        ? (fallback ?? <DefaultSlotEmpty slot={slot} />)
        : items.map((c, i) => (
            <PluginBoundary key={`${c.pluginId}:${i}`} pluginId={c.pluginId}>
              <c.component />
            </PluginBoundary>
          ))}
    </div>
  );
}

function DefaultSlotEmpty({ slot }: { slot: SlotName }) {
  return (
    <div className="slot__empty" data-slot-empty={slot}>
      <span>暂无插件挂接到「{SLOTS[slot]?.title ?? slot}」</span>
    </div>
  );
}
