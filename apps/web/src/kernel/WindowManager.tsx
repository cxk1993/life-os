import { useDesktopStore } from "./store";
import { WindowFrame } from "./WindowFrame";

/**
 * 窗口层：把 store 里所有窗口渲染出来。每个窗口是一个 WindowFrame。
 * 开/关/拖/缩放/聚焦都在各自组件与 store 里完成，这里只负责铺开。
 */
export function WindowManager() {
  const windows = useDesktopStore((s) => s.windows);
  return (
    <>
      {windows.map((w) => (
        <WindowFrame key={w.instanceId} instanceId={w.instanceId} />
      ))}
    </>
  );
}
