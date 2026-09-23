/** desktop.dock 插槽贡献：坞位角标——推送配置态 + 活跃订阅数。 */
import { useQuery } from "@tanstack/react-query";

import { pushApi } from "../api";

export default function DockBadge() {
  const health = useQuery({ queryKey: ["push", "health"], queryFn: pushApi.health });
  const ready = !!health.data?.vapid_ready && !!health.data?.pywebpush_installed;
  const n = health.data?.subscriptions_active ?? 0;
  const title = ready
    ? `推送就绪 · ${n} 个活跃订阅`
    : "推送未就绪（缺 VAPID 密钥或 pywebpush 依赖）";

  return (
    <span className="push-dockbadge" title={title}>
      <span className={ready ? "push-dot push-dot--ok" : "push-dot push-dot--bad"} />
      推送{n > 0 ? ` ${n}` : ""}
    </span>
  );
}
